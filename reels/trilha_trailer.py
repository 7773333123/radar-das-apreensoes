"""Trilha 2: percussão de trailer (original, sintetizada). Tambores graves no compasso, impacto em cada troca
de notícia, crescendo antes da primeira (a maior), cordas graves sustentadas e golpe final no fechamento."""
import json, wave, numpy as np
from scipy.signal import lfilter, butter
SR = 44100
PAL = json.loads(open('palavras.js').read().split('=', 1)[1].rstrip().rstrip(';'))
def t_de(w, depois=0):
    for p, a, b in PAL:
        if p.startswith(w) and a >= depois: return a
    raise SystemExit('sem ' + w)
S1 = t_de('Em'); S2 = t_de('Em', S1 + 1); S3 = t_de('No', S2); FIM = t_de('Siga', S3)
DUR = PAL[-1][2] + 2.5
N = int(SR * DUR); L = np.zeros(N); R = np.zeros(N); rng = np.random.default_rng(7)
def add(sig, t0, g=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N or i < 0: return
    j = min(N, i + len(sig)); x = sig[:j - i] * g
    L[i:j] += x * (1 - max(pan, 0)); R[i:j] += x * (1 + min(pan, 0))
def env(n, at=0.002, q=0.3):
    t = np.arange(n) / SR; return np.clip(t / at, 0, 1) * np.exp(-t / q)
def lp(x, fc): b, a = butter(2, fc / (SR / 2)); return lfilter(b, a, x)
def hp(x, fc): b, a = butter(2, fc / (SR / 2), 'high'); return lfilter(b, a, x)
def taiko(f0=55, q=0.35):
    n = int(0.9 * SR); t = np.arange(n) / SR
    f = f0 + 70 * np.exp(-t / 0.02); corpo = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, q)
    pele = lp(rng.standard_normal(n), 900) * env(n, 0.001, 0.05) * 0.5
    return corpo + pele
def impacto():
    n = int(3.0 * SR); t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-t / 0.05)) / SR) * env(n, 0.001, 0.9)
    ruido = lp(rng.standard_normal(n), 2500) * env(n, 0.001, 0.25) * 0.6
    cauda = lp(rng.standard_normal(n), 400) * env(n, 0.05, 1.2) * 0.25
    return sub + ruido + cauda
def subida(d):
    n = int(d * SR); t = np.arange(n) / SR
    r = hp(rng.standard_normal(n), 1500) * (t / d) ** 2.5 * 0.35
    tom = np.sin(2 * np.pi * np.cumsum(220 + 660 * (t / d) ** 2) / SR) * (t / d) ** 3 * 0.15
    return r + tom
def corda(freqs, t0, d, g):
    n = int(d * SR); t = np.arange(n) / SR; s = np.zeros(n)
    for f in freqs:
        for dt in (-0.25, 0.25):  # serra levemente desafinada = cordas graves
            ph = (t * (f + dt)) % 1.0; s += (2 * ph - 1)
    s = lp(s, 700) / (2 * len(freqs))
    a = np.clip(t / 1.5, 0, 1) * np.clip((d - t) / 1.0, 0, 1)
    add(s * a, t0, g, 0.0)
# ritmo: 90 bpm, tambor grave nos tempos 1 e 3, mais forte e com repique nas trocas
b = 60 / 90; k = 0
while k * b < FIM + 0.5:
    t0 = k * b
    if t0 >= S1 - 0.3:
        add(taiko(55, 0.35), t0, 0.55 if k % 4 == 0 else 0.35, -0.1)
        if k % 4 == 2: add(taiko(82, 0.2), t0 + b / 2, 0.22, 0.25)
    elif k % 2 == 0:
        add(taiko(48, 0.25), t0, 0.18 + 0.3 * t0 / max(S1, 1))
    k += 1
# crescendo até a primeira notícia (a maior) e impacto
add(subida(min(3.5, S1 - 0.2)), max(0, S1 - 3.7), 0.9); add(impacto(), S1 - 0.2, 0.8)
for x in (S2, S3):
    add(subida(1.6), x - 1.8, 0.6); add(impacto(), x - 0.2, 0.7)
corda([73.4, 110.0, 146.8], S1 - 0.2, S2 - S1 + 0.5, 0.30)       # ré menor
corda([65.4, 98.0, 130.8], S2 - 0.3, S3 - S2 + 0.5, 0.30)         # dó
corda([58.3, 87.3, 116.5], S3 - 0.3, FIM - S3 + 0.5, 0.30)        # si bemol
add(impacto(), FIM - 0.2, 0.9)
corda([73.4, 110.0, 146.8, 220.0], FIM - 0.2, DUR - FIM + 0.2, 0.22)
est = np.stack([L, R], 1); est /= max(1e-9, np.abs(est).max()) / 0.85
est[-int(1.5 * SR):] *= np.linspace(1, 0, int(1.5 * SR))[:, None]
with wave.open('trilha2.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((est * 32767).astype('<i2').tobytes())
print('trilha 2', round(DUR, 1), 's; trocas', round(S1, 1), round(S2, 1), round(S3, 1), 'fim', round(FIM, 1))
