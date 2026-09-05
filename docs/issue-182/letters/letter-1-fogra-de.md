<!-- ChromIQ / issue #182 — DRAFT, NOT SENT. Published for review only.
     Names and addresses of individuals are replaced with role placeholders here;
     they live in the working copies, which are not published. -->

# Brief 1 — an die Fogra (deutsche Fassung)

**Status: DRAFT. Nothing has been sent.** This is published so it can be corrected
before a human signs it. Placeholders in angle brackets are for the sender to fill in;
placeholders in square brackets are role names standing in for individuals.

---

Sehr geehrter Herr [Abteilungsleiter Medienvorstufe],

ich möchte Sie fragen, ob die Fogra einer bestimmten Nutzung Ihrer veröffentlichten
Charakterisierungsdaten zustimmen würde. Fällt die Antwort ablehnend aus, ist uns eine
klare Absage ebenso viel wert wie eine Zusage – jedenfalls mehr, als weiter zu mutmaßen.

**Wer wir sind.** ChromIQ ist eine freie Desktop-Anwendung zur Erstellung von
ICC-Druckerprofilen. Das Programm ist quelloffen, steht unter der GNU General
Public License Version 3 und ist unter <https://github.com/itsab1989/ChromIQ>
veröffentlicht. Es wird nicht verkauft, und eine kostenpflichtige Fassung gibt es
nicht. ChromIQ steuert die quelloffenen ArgyllCMS-Werkzeuge und erzeugt einen
Messbericht, der zeigt, wie weit ein Druckergebnis von den beabsichtigten Farben
abweicht. Eingesetzt wird es in der Fotografie, im Fine-Art-Druck und in der
Reproduktion, überwiegend an Tinten- und Tonerdruckern.

**Warum wir eine Referenz brauchen.** Eine Bewertung ist immer ein Vergleich.
Derzeit kann ChromIQ einen Druck nur mit den Sollwerten des eigenen Testcharts
vergleichen – also einen Drucker mit sich selbst. Um über eine anerkannte
Druckbedingung etwas Belastbares aussagen zu können, muss die Messung mit
Sollwerten verglichen werden, und diese Sollwerte sind Ihre
Charakterisierungsdaten. FOGRA51 ist dabei die Datei, die unsere Anwender
ausdrücklich nennen.

**Was wir gern tun würden.** Wir würden die Fogra-Charakterisierungsdaten **so, wie
Sie sie paketieren**, in die Anwendung ChromIQ aufnehmen – zunächst also das
FOGRA51/FOGRA52-Paket, und damit meinen wir alle drei darin enthaltenen Dateien:
`FOGRA51.txt`, `FOGRA51_Spectral.txt` und `FOGRA52.txt`, **einschließlich der
Spektraldatei**; später möglicherweise auch die Fogra-Medienkeil-Teilmengen –
**unverändert**, damit ein Anwender „FOGRA51“
als Referenz für seine Verifizierung auswählen kann, ohne die Datei zuvor selbst
suchen und herunterladen zu müssen. Die Anwendung würde die Fogra überall dort als
Quelle nennen, wo die Daten verwendet werden, und die Datei genau so mitführen, wie
Sie sie veröffentlichen: ohne Änderung, ohne Ableitung, ohne Umwandlung in ein
anderes Format.

**Worum wir bitten – und worum ausdrücklich nicht.**

1. **Eigene Nutzung, und Nutzung einer selbst heruntergeladenen Kopie durch den
   Anwender.** Wir gehen davon aus, dass ein Anwender, der FOGRA51 von Ihrer
   Website herunterlädt und in unserer Software öffnet, dafür niemandes Erlaubnis
   braucht, und dass genau dafür der freie Download da ist. Sollte diese Annahme
   falsch sein, wäre das die wichtigste Auskunft, die Sie uns geben könnten.
2. **Aufnahme einer Kopie in unsere Anwendung** – also die Weitergabe Ihrer Datei
   an unsere Anwender. **Dafür bitten wir um Ihre Erlaubnis.**
3. **Anwendung der Daten, also die Berechnung eines Urteils daraus.** Unsere
   Software würde Ihre Werte nicht nur anzeigen. Das Programm zieht die Messung
   eines Anwenders davon ab und weist das Ergebnis als bestanden oder nicht
   bestanden aus.
   Wir führen das gesondert auf, weil es etwas anderes ist als das bloße Anzeigen
   einer Zahl, und weil wir möchten, dass Sie den tatsächlichen Vorgang beurteilen.
4. **Veränderung der Daten.** Darum bitten wir nicht, und wir würden es nicht tun.
   Wir würden Ihre gemessenen Lab-Werte unverändert als Sollwerte verwenden, und
   sonst nichts.
5. **Berufung auf eine Fogra-Zertifizierung oder -Freigabe.** Darum bitten wir
   nicht, und die Software wird dergleichen auch nicht nahelegen. Angegeben würde
   lediglich, dass eine Messung mit dem Datensatz FOGRA51 verglichen wurde, unter
   Nennung der Fogra als Quelle.

**Eine Anmerkung zu unserer Lizenz, weil sie die Form einer möglichen Erlaubnis
bestimmt.** ChromIQ wird unter der GNU General Public License Version 3
weitergegeben. Diese Lizenz verlangt, dass jeder, der die Software erhält, dieselben
Rechte erhält, die auch wir haben; und sie erlaubt es uns nicht, eine Beschränkung,
der wir selbst zugestimmt haben, an die Empfänger weiterzureichen. Eine Erlaubnis,
die allein uns erteilt würde – also „ChromIQ“ als solchem oder seinen Autoren –,
wäre deshalb praktisch nicht verwertbar: Wer die Software weitergibt, und das darf nach dieser
Lizenz jeder, stünde außerhalb dieser Erlaubnis, und wir müssten die Datei wieder
entfernen. Brauchbar wäre eine Erlaubnis, die mit der Datei auf jeden Empfänger der
Software übergeht. Sollte das mehr sein, als Sie einräumen möchten, ist auch eine
Erlaubnis unter Bedingungen eine wertvolle Auskunft, denn sie kann die kleinere
Variante in der letzten Frage weiterhin zulassen.

**Ausgeliefert haben wir davon bisher nichts.** In keiner veröffentlichten Fassung
von ChromIQ befinden sich Fogra-Daten, und im Quellcode-Repository ebenso wenig.
Diese Anfrage bittet also nicht um die nachträgliche Billigung von etwas bereits
Geschehenem.

**Warum wir fragen, statt anzunehmen.** Wir haben zuerst nach Nutzungsbedingungen
gesucht und nicht nach einer Erlaubnis. Die Downloadseite enthält weder eine Lizenz
noch Nutzungsbedingungen – weder in der deutschen noch in der englischen Fassung;
Ihre AGB regeln Aufträge und Gutachten und nicht die freien Downloads; und das
FOGRA51-Paket selbst enthält ausschließlich die drei Datendateien, ohne Readme und
ohne Lizenz. Wir verstehen das Fehlen einer Lizenz so, dass keine Erlaubnis erteilt
wurde – nicht so, dass keine nötig wäre. Deshalb diese Anfrage und keine
mitgelieferte Kopie Ihrer Datei.

**Der Quellenhinweis, den wir vorschlagen.** Damit Sie keine Formulierung für uns
erfinden müssen, hier der Text, den wir anzeigen würden; selbstverständlich ersetzen
wir ihn durch Ihren, falls Sie einen anderen bevorzugen:

> *Referenzdaten: FOGRA51 © Fogra Forschungsinstitut für Medientechnologien e.V.,
> mit Genehmigung aufgenommen. Die Fogra empfiehlt, zertifiziert und genehmigt
> weder diese Software noch die mit ihr erzielten Ergebnisse. Der jeweils aktuelle
> Datensatz wird unter fogra.org veröffentlicht.*

**Eine gesonderte Frage zum Namen, und das ist keine urheberrechtliche Frage.**
„FOGRA51“ ist nicht nur ein Datensatz, sondern auch ein Name, und Namen können auf
eine Weise geschützt sein, wie es gemessene Zahlen nicht sind. Unabhängig von allem
Vorstehenden: Wäre es aus Ihrer Sicht zulässig, wenn ChromIQ den Namen „FOGRA51“ in
einem Bericht ausschließlich dazu nennt, kenntlich zu machen, womit eine Messung
verglichen wurde? Wir würden ihn als schlichte Bezeichnung verwenden und nie als
Zeichen einer Freigabe. Wir fragen getrennt danach, weil ein Nein zu den Daten kein
Nein zum Namen sein muss – und weil die zweite Antwort darüber entscheidet, ob es
die kleinere Fassung dieser Funktion überhaupt geben kann.

**Vier Fragen, damit wir Ihre Antwort auch umsetzen können.**

* Falls die Aufnahme der Dateien zulässig ist: zu welchen Bedingungen – und kann
  eine solche Erlaubnis so erteilt werden, dass sie auf jeden Empfänger der Software
  übergeht, wie oben beschrieben? Wir fragen bewusst nach dem Paket, wie Sie es
  veröffentlichen, und nicht nach einzelnen Dateinamen, damit die Antwort auch
  `FOGRA51_Spectral.txt` einschließt: eine Erlaubnis für zwei von drei Dateien ließe
  uns einen unvollständigen Download ausliefern, und damit ist niemandem gedient.
* Der Kopf von FOGRA51 lautet `ORIGINATOR "Fogra, www.fogra.org, developed by GMG
  GmbH & Co. KG, Heidelberger Druckmaschinen AG"`. Kann die Fogra dies allein
  gestatten, oder wäre zusätzlich die Zustimmung dieser Unternehmen erforderlich?
* Gilt für eine vom Anwender selbst heruntergeladene Kopie etwas anderes – darf
  unsere Software also eine Datei einlesen, die der Anwender selbst bei Ihnen geholt
  hat, und daraus ein Urteil berechnen?
* Falls die Aufnahme **nicht** zulässig ist: dürfen wir dann (a) aus der Anwendung
  heraus auf Ihre Downloadseite verlinken, sodass der Anwender die Datei selbst
  holt, und (b) den Namen „FOGRA51“ in unserem Bericht nennen, um kenntlich zu
  machen, mit welcher Referenz eine Messung verglichen wurde?

**Wenn wir keine Antwort erhalten.** Wir werden ein Schweigen als Ablehnung werten
und nicht als Zustimmung: Liegt bis zum `<Antwortdatum>` keine Rückmeldung vor,
erscheint ChromIQ ohne Fogra-Daten. Wir schreiben das nur, damit Sie wissen, dass
eine ausbleibende Antwort bei uns nichts Unzulässiges auslöst und dass wir Ihnen
keine Frist setzen wollen.

Jede dieser Antworten hilft uns weiter, auch eine klare Absage. Eine schriftliche
Auskunft von Ihnen ist uns lieber, als Ihre Haltung weiter zu vermuten.

Vielen Dank für Ihre Zeit.

Mit freundlichen Grüßen

`<Name>`
ChromIQ
`<E-Mail>`
`<Postanschrift, falls gewünscht>`
