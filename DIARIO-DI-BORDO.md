# Diario di Bordo — Le Avventure di Chucharon

> Riflessione sul metodo di lavoro usato per costruire questo libro.
> Non un registro di attività, ma una traccia di come si ragiona quando si costruisce
> qualcosa di nuovo insieme — testo, personaggi, immagini, PDF.
> Aggiornato al 4 maggio 2026.

---

## Come si scrive un libro con un assistente AI

La prima cosa che abbiamo capito è che un assistente AI non è uno scrittore — è uno strumento di esternalizzazione. Il tuo compito non è diventare un autore migliore usando l'AI: è imparare a mettere fuori quello che già sai, in una forma che l'AI possa elaborare senza distorcerlo.

Questo ha cambiato il modo in cui ho posto le domande. Invece di "scrivi un capitolo su Leo", il lavoro è stato: chi è Leo? Cosa sente? Cosa vogliono i suoi genitori? Cosa rappresenta questa scena nel percorso emotivo del libro? L'AI ha trasformato le risposte in testo — ma le risposte erano mie.

Il rischio principale di questo metodo è la deriva: se non si definisce bene la voce e il tono all'inizio, l'AI riempie i silenzi con le sue convenzioni — che tendono verso il sentimentale, il didascalico, il generico. Abbiamo evitato questo costruendo `book.config.json` come primo atto — non come burocrazia, ma come specchio della voce che volevamo.

---

## Il metodo della voce

La sezione `author_voice` in `book.config.json` non è una lista di preferenze estetiche. È un sistema di vincoli negativi: **cosa non deve mai apparire nel testo**.

> `"avoid": "sentimentalismo eccessivo, linguaggio letterario, spiegazioni troppo lunghe, moralismo"`

Questo è il metodo: definire i confini prima del contenuto. Un'AI sa costruire frasi corrette in qualunque stile — ma senza confini espliciti, tende verso la media statistica di tutto ciò che ha visto. La media di un libro per bambini è sentimentale, didascalico e moralista. Quindi i confini sono più importanti delle istruzioni positive.

La parte più difficile è stata il ritmo. "Frasi brevi e visive" è un'istruzione che suona bene ma è ambigua. Quello che ha funzionato è stato produrre testo, leggerne alcuni paragrafi ad alta voce, e correggere dove il ritmo si rompeva. L'AI non sente il ritmo — lo misura. Tu lo senti. La correzione avviene nel dialogo tra le due cose.

---

## Il metodo delle parentesi (e perché le abbiamo eliminate)

Il testo originale usava spesso questo pattern:
> *(in corsivo tra parentesi — una nota a parte, quasi un commento del narratore)*

È un pattern che sembra utile: stacca la voce del narratore da quella della scena, crea un effetto "strizzata d'occhio". Ma su carta, in un picture book, funziona meno di quanto sembri. Il lettore ad alta voce si trova a gestire due livelli di testo — e quasi sempre sceglie uno solo.

La decisione è stata: **tutto è narrazione, tutto è principale, non esistono note a margine**. Il contenuto delle parentesi non andava eliminato — andava integrato. Questo è un principio generale: non si toglie mai un'idea, si cambia il modo in cui entra nel testo.

Il metodo operativo: per ogni parentesi, la domanda era "se questa frase fosse narrazione normale, come suonerebbe?" Spesso diventava più forte, non meno.

---

## Il metodo dei personaggi

I profili dei personaggi in `characters/` non sono biografie. Sono **mappe comportamentali**: dato qualsiasi momento narrativo, come si muove questo personaggio? Cosa dice? Cosa non dice? Dove guarda?

Il metodo dell'intervista — una domanda alla volta, con pausa tra una risposta e l'altra — serve a impedire che il personaggio si costruisca tutto in una volta in astratto. Un personaggio costruito in astratto è coerente ma piatto. Un personaggio costruito risposta per risposta, seguendo la logica delle domande, sviluppa contraddizioni — e le contraddizioni sono la cosa che lo rende credibile.

La domanda più utile non era "descrivi il personaggio" ma "cosa fa quando è sotto pressione?" Il comportamento sotto pressione rivela più di qualsiasi descrizione statica.

Chucharon è stato il caso più difficile perché non è un bambino e non è un adulto — è un oggetto animato con un punto di vista. Il suo profilo ha richiesto di decidere una cosa prima di tutto il resto: cosa sa che gli altri non sanno? La risposta ha determinato tutto il resto del suo comportamento narrativo.

---

## Il metodo dei prompt visivi (il problema più complesso del progetto)

La generazione di illustrazioni con AI ha un problema fondamentale: **il modello non ha memoria visiva tra una generazione e l'altra**. Ogni immagine nasce da zero. Se vuoi consistenza visiva tra 25 illustrazioni, devi portare quella consistenza dentro ogni prompt — non puoi affidarti a "ricorda come era Leo nella scena precedente".

Questo è il problema che ha richiesto più iterazioni e ha prodotto il metodo più interessante.

### Primo approccio: descrizione nel prompt

Il primo istinto è stato: aggiungi una descrizione dettagliata del personaggio nel prompt. "Leo, neonato cicciotto, tutina celeste con stelline bianche." Funziona per i dettagli salienti — ma non è abbastanza per fermare la deriva. Il modello interpreta, non copia.

### Secondo approccio: ripetizione sistematica (l'ANCHOR)

Se una descrizione in un punto non basta, la stessa descrizione in ogni punto. Il `CHAPTER CHARACTER ANCHOR` è questo: lo stesso blocco di testo, identico, in cima a ogni file di scena del capitolo. Cinque volte la stessa descrizione di Leo — outfit, capelli, corporatura.

Questo ha migliorato la consistenza all'interno di un capitolo. Ma ha creato un problema nuovo.

### Il problema dei capitoli multipli: la confusione incrociata

Con tre famiglie diverse (Leo, Sofia, Marco) il modello cominciava a mescolare i personaggi tra capitoli. La scena C1-04 generava Leo con gli occhiali — che sono di Marco, non di Leo. Il padre di Marco con i capelli scuri — che sono di altri.

Il motivo è sottile: il modello ha letto così tante descrizioni di bambini con occhiali, padri con grembiule, madri con chignon, che quando queste caratteristiche appaiono in un prompt "confinante", tendono a contaminare la generazione.

### Terzo approccio: l'identità negativa (il VISUAL IDENTITY block)

La svolta è stata capire che **definire un personaggio in positivo non basta — bisogna definirlo in negativo rispetto agli altri**. Non "Leo ha i capelli biondi" ma "Leo è l'unico bambino in tutto il libro con i capelli biondi — se il bambino ha i capelli scuri, è il bambino sbagliato."

Questo è il `VISUAL IDENTITY` block: ogni personaggio viene descritto come unico nel libro intero, con negative esplicite che rimandano alle caratteristiche degli altri personaggi. Il modello non deve più *scegliere* tra interpretazioni — viene guidato attraverso l'esclusione.

Il formato è stato calibrato per essere massimamente direttivo:
> "LEO: the ONLY baby in this book who is EXTRAORDINARILY CHUBBY — with soft BLONDE hair. NO GLASSES. If the baby has dark hair, glasses, or is thin, **it is the wrong baby**."

La frase finale — "it is the wrong baby" — è insolita in un prompt. Ma funziona perché forza il modello a usare la descrizione come criterio di verifica, non solo come istruzione.

### Quarto approccio: il tag inline (MUST BE EXACT)

Anche con ANCHOR e VISUAL IDENTITY, il modello a volte "dimenticava" i dettagli nel mezzo di una scena complessa. Il tag inline — inserito nel corpo del prompt al primo riferimento a ogni personaggio — riporta la descrizione critica esattamente nel punto dove serve:

> *"his father (FATHER'S APPEARANCE — MUST BE EXACT: light brown hair, blond stubble, grey t-shirt, navy sweatpants, barefoot)"*

Il principio: **porta l'informazione il più vicino possibile al punto di utilizzo**. Non fare affidamento sul fatto che il modello "ricordi" quanto detto cento token prima.

### Il sistema a tre livelli

Il risultato finale è un sistema stratificato:
1. **CHAPTER CHARACTER ANCHOR** — top del file, identità base
2. **VISUAL IDENTITY block** — unicità e negative cross-references
3. **Tag inline MUST BE EXACT** — ridondanza locale nel corpo della scena

La ridondanza è intenzionale e necessaria. In un contesto come questo, ripetere non è rumore — è segnale.

---

## Il metodo del debugging visivo

Quando un'immagine generata era sbagliata, il metodo non era "rigenera e spera". Era:

1. **Identifica il sintomo preciso** — non "il personaggio è sbagliato" ma "il bambino ha i capelli scuri invece di biondi" o "il padre indossa un grembiule invece della maglietta grigia"
2. **Risali alla causa nel prompt** — dov'è la lacuna? C'è un'istruzione contraddittoria? L'anchor dice una cosa e il body ne dice un'altra?
3. **Correggi il punto specifico** — non riscrivere tutto, modifica solo il punto causa
4. **Aggiungi ridondanza** — se un'istruzione non bastava, aggiungila anche nel posto più vicino al problema

Il caso di Leo con i capelli scuri in C1-04 è emblematico: l'anchor originale diceva "dark brown hair" (sbagliato — Leo è biondo). Le prime tre scene erano state generate correttamente per ragioni probabilistiche, ma C1-04 aveva seguito l'anchor troppo fedelmente. Il bug era nell'anchor, non nella scena. Correggere solo C1-04 avrebbe nascosto il problema — abbiamo corretto tutti e cinque i file C1.

---

## Il metodo del layout PDF

Il PDF è il punto in cui il lavoro di scrittura e il lavoro visivo si incontrano. I problemi qui hanno una natura diversa: non sono di interpretazione (come con le illustrazioni) ma di geometria e tipografia.

### Il principio: capire prima di correggere

Il primo istinto quando qualcosa non funziona in un PDF è cambiare parametri a caso finché qualcosa migliora. Questo non funziona — si finisce per risolvere un sintomo e crearne tre nuovi.

Il metodo giusto è: **prima capire perché il comportamento attuale è quello che è, poi modificare il parametro corretto**.

**Esempio: pagine canzone non a piena larghezza**

Sintomo: il testo delle canzoncine non raggiunge il margine destro.
Tentativo sbagliato: alzare il `SONG_TEXT_ZONE_H` al 50% → il testo occupava tutta la larghezza ma la zona era troppo alta.
Causa vera: il testo veniva reso riga per riga (`display_lines = raw_lines`). Ogni verso di una canzoncina è corto per definizione — "El Chucharito, El Chucharito" non raggiunge mai il margine destro, indipendentemente dalla dimensione del font.
Soluzione: concatenare tutte le righe in un unico paragrafo, esattamente come le pagine normali, e lasciare che `wrap_text()` divida secondo la larghezza disponibile. Il font fa il resto.

**Esempio: nota musicale come quadratino**

Sintomo: `♪` stampa come box vuoto.
Causa: il glifo U+266A non è presente nel font Helvetica né in Nunito.
Tentativo che potrebbe sembrare ovvio: usare un font che lo contiene. Ma questo richiede di caricare un terzo font solo per un carattere decorativo.
Soluzione più pulita: rimuovere le emoji musicali (`🎵`, `🎶`) in `clean_text()`. Le pagine canzone sono già visivamente distinte — bold + skew pseudo-italic + zona dedicata. Il simbolo è decorativo, non semantico. Toglierlo non impoverisce nulla.

---

## Il principio generale che emerge

Guardando tutto il lavoro insieme, c'è un principio che si ripete in ogni fase:

**La chiarezza dell'istruzione è inversamente proporzionale all'ambiguità del risultato.**

Vale per i prompt visivi: più l'istruzione è specifica (fino ai negativi espliciti), meno il modello inventa.
Vale per la voce narrativa: più i confini sono definiti (cosa non fare), più il testo rimane fedele al registro.
Vale per il layout: più si capisce la causa (non il sintomo), più la correzione è pulita.

L'AI amplificherà sempre quello che le dai — bene o male. Se le dai ambiguità, produrrà variazioni. Se le dai precisione, produrrà consistenza. Il lavoro dell'autore è, in gran parte, **ridurre l'ambiguità prima che il sistema la interpreti**.

---

## Cosa non abbiamo ancora risolto

- La consistenza visiva è ancora fragile: ogni rigenerazione è un rischio. Il sistema a tre livelli riduce il problema ma non lo elimina — dipende dalla qualità del modello in quel momento.
- La voce narrativa ha ancora zone dove il tono scivola verso il generico — i passaggi di transizione tra scene, in particolare. Richiedono lettura ad alta voce e revisione manuale.
- Il PDF funziona, ma non è stato ancora verificato in stampa fisica. La zona testo al 26% è una stima — su carta potrebbe richiedere aggiustamenti.

---

*Questo diario va aggiornato ogni volta che si affronta un problema nuovo e si trova un metodo che funziona. Non le cose fatte — come si è ragionato per farle.*

---

## Changelog

> Registro cronologico del lavoro svolto. Concentrato su scrittura e personaggi.
> La parte illustrativa è sintetizzata alla fine.

---

### 2026-04-18 — Primo draft Capitolo 1 (Leo) + primo ciclo di demolizione

**Cosa è successo**
Scritto il primo draft del Capitolo 1 — La tummy time di Leo. Primo ciclo di demolizione immediato.

**Problemi trovati e risolti**
- La canzoncina non scansionava su La Cucaracha → riscritta con "El Chucharito" come incipit metrico
- L'immagine della "tartaruga a molla" era sottoscritta — non abbastanza buffa → rinominata "tartaruga messicana" e collegata all'invocazione di Chucharon: il genitore dice "tartaruga messicana" e quella parola lo chiama
- La definizione di tummy time era didascalica, rompeva il ritmo → eliminata
- "Funziona davvero" era una promessa impossibile → sostituita con "provate a vedere se funziona"

**Versione raggiunta**: v2.0

---

### 2026-04-19 — Secondo ciclo di demolizione Capitolo 1

**Problemi trovati e risolti**
- La nota ai genitori in fondo al capitolo rompeva il finale emotivo → eliminata, sostituita con una scena narrativa: Chucharon balla davanti a Leo
- Leo non aveva personalità propria — era solo "il bambino che non vuole" → aggiunta identità: cicciotto, strafatto di latte materno, percentile altissimo
- Leo non reagiva al suo traguardo — il finale era piatto → aggiunto il rigurgito di latte come gesto di soddisfazione: fisica, comico, perfetto

**Versione raggiunta**: v3.0

---

### 2026-04-20 — Terzo ciclo di demolizione Capitolo 1

**Problemi trovati e risolti**
- Il gesto preparatorio di Chucharon (il "rituale" prima della trasformazione) non arrivava al lettore → trasformazione resa esplicita: da "messicano in siesta" a raggiante. Il rituale sombrero→El Chucharito stabilito in modo permanente
- "Coda del cappellino" — un'immagine inventata, il sombrero non ha una coda → rimpiazzata: Chucharon raccoglie il cappellino, lo fa volteggiare, e dal giro nasce l'arcobaleno
- Le istruzioni per cantare la canzone arrivavano *dopo* la canzone → anticipate nella trasformazione, così il lettore sa già su che melodia cantare
- "Chucharon strizza l'occhio" — ma Chucharon ha occhi? → risolto: gli occhi di El Chucharito vengono stabiliti nella scena di trasformazione, la strizzata finale è coerente

**Versione raggiunta**: v3.1 — Capitolo 1 chiuso

---

### 2026-04-21 — Draft + demolizione Capitolo 2 (Sofia) e Capitolo 3 (Marco)

#### Capitolo 2 — I dentini di Sofia

**Draft**
Sofia: magra, ossuta, faccia perennemente seria. I dentini fanno male, il metodo è mordere tutto. Le espadrillas messicane del padre diventano il vettore che invoca Chucharon — e anche il gancio comico finale (Sofia sputa la paglia).

**Demolizione (ciclo 1, 5 problemi)**
- "Lo sta facendo" senza referente — il climax era vago → dialogo specifico: la mamma celebra le espadrillas lasciate, il papà commenta la paglia messicana
- L'introduzione di Chucharon era identica al Capitolo 1 → riscritta: Chucharon arriva già gobbuto, baffi ricadenti, aria da siesta interrotta — differenziato
- I denti di Sofia "apparivano magicamente" dopo l'incontro con Chucharon → corretto: i denti erano già suoi, Chucharon dà solo il comfort; parentetica rimossa
- La mamma parlava italiano/spagnolo misto → resa in italiano puro — la parola "Messico" fa tutto il lavoro necessario da sola
- Il finale non menzionava più Chucharon → aggiunta: Sofia ricorderà i denti bianchi di El Chucharito — mai, in tutta la sua vita

**Versione raggiunta**: v1.5 — Capitolo 2 chiuso

---

#### Capitolo 3 — La pappa di Marco

**Draft**
Marco: occhialini wire frames senza lenti (li ha trovati per terra un giorno e non li ha mai tolti). Non piange, non urla — tiene comizi in una lingua inventata. La pappa raffredda. Il papà aveva scoperto il trucco delle piramidi Maya: documentario acceso, Marco a bocca aperta, cucchiaio dentro. La mamma lo ha scoperto. Il trucco è proibito. I genitori sono in stallo. Il papà, esasperato, dice "piramidi messicane" — e Chucharon arriva.

**Demolizione (ciclo 1, 2 problemi)**
- La trasformazione di Chucharon era "veloce" senza giustificazione → Chucharon legge la stanza: vede gli occhi della mamma passare da "fulminanti" a "feroci", capisce che deve essere rapido per salvare il papà. La velocità diventa un atto di lettura della situazione, non di fretta
- "Con i gradini e tutto" — filler, senza immagine → sostituito con "l'ombra del serpente che scendeva lungo le scale": l'immagine iconica di Chichén Itzá all'equinozio, concreta e bellissima

**Versione raggiunta**: v1.2 — Capitolo 3 chiuso

---

### 2026-04-22 — Draft + demolizione Prologo ed Epilogo

#### Prologo — Chucharon si sveglia

**Draft**
Elena al parco. Giornata perfetta. La famiglia se ne va — ma non proprio tutti. Chucharon rimane nell'erba alta, nascosto. Si sveglia. Capisce che il suo bambino non c'è più. Decide di partire.

**Demolizione (ciclo 1, 3 problemi)**
- La sparizione di Elena sembrava immotivata per un primo lettore → aggiunta la battuta di Chucharon: "Elenita sei tu? Vamos a veder!" — la sparizione diventa una ricerca attiva, non un abbandono
- "Solo quella frase" — meta-commento del narratore, ridondante e debole → sostituito con azione fisica: "Frrrrr..." + balla di fieno rotolante (immagine da western messicano, buffa e precisa)
- "I baffi si mossero" — direzione non specificata, ambiguo → chiarito: "ancora ricadenti — fremettero" — stabilisce un terzo stato espressivo (né siesta né trionfo: allerta) che sarà usato ogni volta che Chucharon sente un bambino in difficoltà

**Versioni raggiunte**: v1.1 → v1.2 → v1.3 — Prologo chiuso

---

#### Epilogo — Chucharon trova il suo bambino

**Draft**
Elena al parco, più grande. Il monopattino, la velocità, la posa da motociclista Harley. Si allontana. Si avvicina alla strada. Chucharon si trasforma in El Chucharito e la ferma. Canzone. Ritrovo.

**Demolizione (ciclo 1, 5 problemi)**
- Il ritardo tra il momento in cui Chucharon riconosce Elena e il momento in cui agisce sembrava artificioso → motivato: serve El Chucharito, non Chucharon, perché solo lui è abbastanza veloce e abbastanza rumoroso da fermare Elena prima della strada
- La canzone celebrava la reunion mentre il problema reale era la sicurezza → canzoncina riscritta per includere il tema safety + il ritrovo, nell'ordine giusto
- Elena non era mai stata introdotta prima dell'epilogo — il lettore non aveva investimento emotivo → costruito profilo completo del personaggio, con "tutti insieme" come frase ricorrente e la paura della separazione come suo nucleo emotivo. Entrambi da integrare nel testo dell'epilogo
- El Chucharito disegnava se stesso nell'aria — autoriflessivo e straniante → sostituito con il paesaggio del confine messicano: montagne, tramonto, alberi, strada sterrata. Ciò che Chucharon stava cercando di tornare a casa
- Il finale parlava solo di Chucharon — Elena era una comparsa nel suo stesso epilogo → Elena chiude il viaggio con la sua frase: "tutti insieme". L'ultima parola del libro è sua

**Versione raggiunta**: v1.5 — Epilogo chiuso

---

### 2026-04-25 — Decisione stilistica definitiva

A revisione dei capitoli completata, una decisione trasversale su tutto il libro:

**Le parentesi vanno eliminate.** Ogni passaggio `*(in corsivo tra parentesi)*` diventa narrazione regolare — stessa voce, stesso contenuto, integrato nel flusso principale senza segnali di "a parte".

**La parte narrativa va arricchita.** I passaggi narrativi tra i dialoghi non sono appunti di scena — sono narrazione a pieno titolo, evocativa e visiva.

La voce frammentata e i dialoghi con trattino restano invariati. Non si cambia lo stile di base — si elimina il doppio registro.

Motivazione dichiarata dall'autore: *"a me piace come lo abbiamo scritto — va arricchita la parte narrativa e tolta dalle parentesi."*

Questa decisione si applica a tutti i capitoli in ogni futura revisione.

---

### 2026-04-25 → 2026-05-04 — Profili personaggi (completati in parallelo alla scrittura)

I quattro profili in `characters/` sono stati costruiti con il metodo dell'intervista — una domanda alla volta, con pausa tra risposta e risposta.

**Chucharon** — Il profilo più complesso: non è un bambino, non è un adulto, è un oggetto animato con un punto di vista. La domanda fondamentale è stata: *cosa sa che gli altri non sanno?* La risposta ha determinato tutto il resto. La ferita (perdere Elena), la credenza (se un bambino è in difficoltà si interviene sempre), il punto cieco (crede di potersi sentire completo solo ritrovando Elena — non sa ancora che può farlo con ogni bambino). Il rituale sombrero→El Chucharito come firma comportamentale.

**Elena** — Figlia dell'autore. Il profilo mescola osservazione diretta e scelta narrativa. La contraddizione centrale: sembra che aspetti il permesso per esistere, invece stava solo studiando il campo. "Tutti insieme" come frase ricorrente. La voce storpiata (pescerutto, io sono giocando) come oro narrativo da usare con parsimonia. Il monopattino come oggetto che esternalizza il suo conflitto: abbastanza grande per la velocità, abbastanza piccola da non sapere quanto si è allontanata.

**Sofia** — Costruita per contrasto con Leo. Leo: cicciotto, passivo, piangeva e aspettava. Sofia: magra, attiva, urlava e attaccava. Due bambini, un unico messaggio: *questo fa male e voglio che smetta.* La fisica del finale (sputa la paglia delle espadrillas) è l'equivalente del rigurgito di Leo — comica, corporea, perfetta.

**Marco** — La lingua inventata come sistema narrativo. Marco non balbetta e non è incomprensibile per caso — segue una logica interna precisa, e chi lo ascolta finisce per rispondergli come se avesse capito. Il meccanismo delle piramidi (apre la bocca automaticamente) è il suo "tummy time" — il genitore lo conosce, lo usa, ci litiga.

---

### Note sulle illustrazioni e il PDF (sintesi)

In parallelo alla scrittura, è stata costruita la pipeline tecnica per generare le illustrazioni con AI (Google Gemini) e assemblarle in PDF (ReportLab).

Il lavoro principale in questa area ha riguardato la **consistenza visiva**: il modello non ha memoria tra una generazione e l'altra, quindi ogni prompt deve portare dentro di sé tutta l'informazione necessaria. Sono stati risolti problemi di capelli che cambiavano colore tra scene, famiglie scambiate tra capitoli, ambientazioni incoerenti. La soluzione è un sistema a tre livelli di ridondanza nei prompt (anchor + disambiguazione con negativi espliciti + tag inline).

Per il PDF: risolti bug sulla nota musicale che stampava come quadratino, e sulle pagine canzone che non riempivano la larghezza. Entrambi risolti identificando la causa prima di intervenire.

*Per i dettagli metodologici su questa parte, vedi le sezioni precedenti di questo diario.*
