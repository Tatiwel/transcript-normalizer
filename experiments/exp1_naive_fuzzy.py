import csv, re, sys, unicodedata, yaml
from collections import defaultdict, Counter
from rapidfuzz import fuzz

USAR_VARIANTES = '--variantes' in sys.argv
LIMIAR = int(next((a.split('=')[1] for a in sys.argv if a.startswith('--limiar=')), 80))

def norm(s):
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9$ ]+', ' ', s).strip()

termos = yaml.safe_load(open('fixtures/R2Qgz8tFWVI/legacy/termos.yaml'))['termos']
cands = []  # (string_normalizada, termo_canonico)
for t in termos:
    for s in [t['termo']] + t.get('apelidos', []) + (t.get('variantes', []) if USAR_VARIANTES else []):
        cands.append((norm(s), t['termo']))

linhas = [l for l in open('fixtures/R2Qgz8tFWVI/legenda.txt', encoding='utf-8') if not l.startswith('#')]

propostas = defaultdict(list)  # (ts) -> [(trecho, termo, score)]
for l in linhas:
    ts, txt = l.strip().split(' ', 1)
    pal = [w for w in re.sub(r'[^\wÀ-ÿ$%,.]+',' ',txt).split() if re.search(r'\w',w)]
    pal=[w.strip('.,') for w in pal]
    for n in (1, 2, 3):
        for i in range(len(pal) - n + 1):
            trecho = ' '.join(pal[i:i+n])
            tn = norm(trecho)
            if len(tn) < 2: continue
            melhor = max(((fuzz.ratio(tn, c) if len(tn)>=5 and len(c)>=5 else (100 if tn==c else 0), termo, c) for c, termo in cands), default=(0, None, None))
            if melhor[0] >= LIMIAR and norm(melhor[1]) not in tn and not any(norm(a) in tn for t in termos if t['termo']==melhor[1] for a in t.get('apelidos',[])):
                propostas[ts].append((trecho, melhor[1], melhor[0]))

gab = list(csv.DictReader(open('fixtures/R2Qgz8tFWVI/legacy/gabarito.csv', encoding='utf-8-sig')))
escopo = [g for g in gab if g['termo_canonico'] and g['status'] != 'manter']
fora = [g for g in gab if not g['termo_canonico']]
manter = [g for g in gab if g['status'] == 'manter']

acertos, perdidos = [], []
por_termo = defaultdict(lambda: [0, 0])
usadas = set()
for g in escopo:
    ok = None
    for p in propostas.get(g['timestamp'], []):
        if p[1] == g['termo_canonico'] and (norm(g['trecho_errado']) in norm(p[0]) or norm(p[0]) in norm(g['trecho_errado'])):
            ok = p; break
    por_termo[g['termo_canonico']][1] += 1
    if ok:
        acertos.append((g, ok)); por_termo[g['termo_canonico']][0] += 1
        usadas.add((g['timestamp'], ok[0]))
    else:
        perdidos.append(g)

# falsos positivos: propostas que nao casam com nenhuma linha do gabarito em escopo
gab_por_ts = defaultdict(list)
for g in gab: gab_por_ts[g['timestamp']].append(g)
fp = []
for ts, ps in propostas.items():
    for p in ps:
        if (ts, p[0]) in usadas: continue
        # dedupe: sub-trecho de uma proposta ja usada na mesma linha
        if any(norm(p[0]) in norm(u[1]) or norm(u[1]) in norm(p[0]) for u in usadas if u[0] == ts): continue
        fp.append((ts, p))

print(f'modo: {"com variantes" if USAR_VARIANTES else "so termo+apelidos"}  limiar={LIMIAR}')
print(f'gabarito em escopo (tem termo canonico): {len(escopo)}   fora de escopo: {len(fora)}   manter: {len(manter)}')
print(f'acertos: {len(acertos)}   perdidos: {len(perdidos)}   falsos positivos: {len(fp)}')
print('\npor termo (acertos/total):')
for t, (a, n) in sorted(por_termo.items(), key=lambda x: -x[1][1]):
    print(f'  {t:20s} {a:3d}/{n}')
print('\nperdidos:')
for g in perdidos: print(f"  {g['timestamp']:6s} {g['trecho_errado']!r} -> {g['termo_canonico']}")
print('\nfalsos positivos (unicos por trecho):')
c = Counter((p[0], p[1]) for ts, p in fp)
for (tr, termo), n in c.most_common(40): print(f'  {n:3d}x {tr!r} -> {termo}')
print('\nmexeu nas linhas manter?')
for g in manter: print(f"  {g['timestamp']} {g['trecho_errado']!r}: {propostas.get(g['timestamp'])}")
