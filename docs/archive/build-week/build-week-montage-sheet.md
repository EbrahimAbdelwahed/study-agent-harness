# Build Week — foglio di montaggio

Audio: `docs/archive/build-week/build-week-voiceover-elevenlabs.txt` (8 blocchi, generati separatamente)
Video sorgente: external Build Week Media Archive, `Study Agent Harness - Launch Video.mp4` — 138s
Montaggio target: **3:55** (235s)

Durate audio = **stima a 130 wpm + pause dei break tag**. Da rimisurare con
`ffprobe` sui file reali prima di bloccare il taglio (vedi in fondo).

## Timeline

| # | Blocco | IN | OUT | Durata | Scena nel 138s | Ora | Delta |
|---|---|---|---|---|---|---|---|
| 1 | Opening cards | 0:00.00 | 0:11.00 | 11.0s | 0:00–0:06 | 6s | +5.0s |
| 2 | Title | 0:11.00 | 0:22.00 | 11.0s | 0:06–0:16 | 10s | +1.0s |
| 3 | Architecture | 0:22.00 | 0:38.40 | 16.4s | 0:16–0:29 | 13s | +3.4s |
| 4 | Terminal demo | 0:38.40 | 1:09.80 | 31.4s | 0:29–0:58 | 29s | +2.4s |
| 5 | Refresh/Resume/Replay | 1:09.80 | 2:07.70 | 57.9s | 0:58–1:26 | 28s | **+29.9s** |
| 6 | State outside model | 2:07.70 | 2:33.80 | 26.1s | 1:27–1:42 | 15s | +11.1s |
| 7 | Codex flywheel | 2:33.80 | 3:31.70 | 57.9s | 1:42–2:06 | 24s | **+33.9s** |
| 8 | Endcard | 3:31.70 | 3:55.00 | 23.3s | 2:06–2:18 | 12s | +11.3s |

Stacco a nero già presente nel sorgente a **1:26–1:27** (fra blocco 5 e 6).

## Due problemi da risolvere prima di montare

### 1. Sfori il tuo stesso brief

`docs/archive/build-week/build-week-submission.md` fissa il formato a **2:40–2:50**.
Questo montaggio sta a **3:55** — 65s oltre il limite alto.
Da decidere: aggiornare il brief, o tagliare ~65s.

### 2. Blocchi 5 e 7 sono metà del film

116s su 235s = **49%**, e sono gli unici due che più che raddoppiano.
Non è solo questione di durata — hanno animazione interna:

- **Blocco 5** (terminale): la battitura va ri-temporizzata, non stirata.
  Righe che compaiono a metà velocità sembrano un lag, non un ritmo.
- **Blocco 7** (flywheel): 5 chip su 57.9s = **11.6s per chip**, contro i 4.8s
  attuali. Una chip statica per 11 secondi legge come video bloccato.
  Se tieni il blocco 7 intero servono sotto-stati per chip (es. il bead che si
  illumina, la review che dà il verde), altrimenti va accorciato il testo.

Se tagli 65s, i due blocchi sono anche i candidati naturali: il punto più
denso e meno decodificabile da un giudice è l'elenco
`GPT-5.6-Sol / Luna / Terra / Sol` a metà del blocco 7 (~20s).

## Prima di bloccare il taglio

Le durate qui sono stimate. Misura i file reali:

```bash
for f in block_*.mp3; do printf "%s  " "$f"; ffprobe -v error -show_entries format=duration -of csv=p=0 "$f"; done
```

Poi riporta i valori in questa tabella: la voce reale può stare ±15% dalla
stima, che su 235s significa fino a ±35s.
