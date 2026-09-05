<!-- ChromIQ / issue #182 — DRAFT, NOT SENT. Published for review only.
     Names and addresses of individuals are replaced with role placeholders here;
     they live in the working copies, which are not published. -->

# Letter 1 — to Fogra (English)

**Status: DRAFT. Nothing has been sent.** This is published so it can be corrected
before a human signs it. Placeholders in angle brackets are for the sender to fill in;
placeholders in square brackets are role names standing in for individuals.

---

Dear [head of the Prepress department],

I am writing to ask whether Fogra would permit a particular use of your published
characterization data. If the answer is no, a plain no is just as useful to us as
a yes, and we would rather have it than keep guessing.

**Who we are.** ChromIQ is a free desktop application for making ICC colour
profiles for printers. It is published as open source under the GNU General Public
License, version 3, at <https://github.com/itsab1989/ChromIQ>. It is not sold and
there is no paid edition. It drives the open-source ArgyllCMS tools and produces a
measurement report which tells a user how far a printed result is from the colours
that were intended. Its users are photographers, fine-art printers and repro staff
working on inkjet and toner devices.

**Why we need a reference.** A verdict is a comparison, and at present ChromIQ can
only compare a print with the chart's own design values — which is to say, a
printer with itself. To tell a user anything meaningful about a recognised printing
condition, the report has to compare their measurement with an aim, and the aim is
your characterization data. FOGRA51 in particular is the file our users name.

**What we would like to do.** We would like to include the Fogra characterization
data **as you package it** — that is, the FOGRA51/FOGRA52 download in the first
instance, and by that we mean all three files it contains, `FOGRA51.txt`,
`FOGRA51_Spectral.txt` and `FOGRA52.txt`, **including the spectral file**; and
possibly the Fogra MediaWedge subsets later — **unaltered**, inside the ChromIQ
application, so that a user
can select "FOGRA51" as the reference for their verification without first having
to find and download the file. The application would name Fogra as the source
wherever the data is used, and would carry the file exactly as you publish it: no
modification, no re-derivation, no repackaging into another format.

**What we are asking, and what we are not.**

1. **Using the data ourselves, and a user using their own copy.** We assume that a
   user who downloads FOGRA51 from your website and opens it in our software needs
   no permission from anyone, and that this is what the free download is for. If
   that assumption is wrong, that is the most important thing you could tell us.
2. **Including a copy inside our application** — that is, redistributing your file
   to our users. **This is what we are asking permission for.**
3. **Applying the data — computing a verdict from it.** Our software would not
   only show your values; it would subtract a user's measurement from them, and
   print a pass or a fail. We mention this separately because it is a different
   act from displaying a number, and we would rather you judged the real one.
4. **Modifying the data.** We are not asking for this and would not do it. We
   would use your measured Lab values as they stand, as the aim, and nothing else.
5. **Claiming any Fogra certification or approval.** We are not asking for this
   and the software will not imply it. It would say only that a measurement was
   compared with the FOGRA51 data set, naming Fogra as its source.

**One thing about our licence, because it shapes what a permission would have to
say.** ChromIQ is distributed under the GNU General Public License, version 3. That
licence requires that everyone who receives the software receives the same rights
we have, and it does not allow us to pass on a restriction to them that we have
accepted ourselves. So a permission granted to us alone — to "ChromIQ", or to its
authors — would unfortunately be of no practical use: the first person to
redistribute the software, which the licence permits anyone to do, would fall
outside it, and we would have to remove the file again. What would work is a
permission that travels with the file to everyone who receives the software. If
that is more than you want to give, a permission with conditions is still worth
telling us about, because it may still allow the smaller option in the last
question below.

**We have shipped none of it yet.** No released version of ChromIQ contains any
Fogra data, and none is in our source repository. Nothing here is a request to
bless something already done.

**Why we are asking rather than assuming.** We looked for terms of use before we
looked for permission. The download page carries no licence and no terms of use, in
either the English or the German version; your General Terms and Conditions govern
purchase orders and expert opinions rather than the free downloads; and the FOGRA51
package itself contains only the three data files, with no readme and no licence. We
take the absence of a licence to mean that no permission has been given, not that
none is needed — which is why this letter exists rather than a bundled copy of your
file.

**The attribution we would propose.** So that you do not have to invent wording for
us, here is what we would display, and we would of course use yours instead if you
prefer:

> *Reference data: FOGRA51 © Fogra Forschungsinstitut für Medientechnologien e.V.,
> included with permission. Fogra does not endorse, certify or approve this software
> or any result it produces. The current data set is published at fogra.org.*

**A separate question about the name, which is not a copyright question.** "FOGRA51"
is a name as well as a data set, and a name can be protected in ways that measured
numbers are not. Quite apart from everything above: is it acceptable to you that
ChromIQ prints the name "FOGRA51" in a report solely to identify what a measurement
was compared with? We would use it as a plain identifier and never as a mark of
approval. We ask separately because a "no" to the data need not be a "no" to the
name, and the second answer is the one that decides whether the reduced version of
this feature can exist at all.

**Four questions, so that we can act on your answer.**

* If including the files is permitted, on what terms — and can that permission be
  one that travels to everyone who receives the software, as described above? We ask
  about the package as published rather than about named files, so that the answer
  covers `FOGRA51_Spectral.txt` too; a permission for two of the three would leave us
  shipping an incomplete download, which serves nobody.
* The header of FOGRA51 reads `ORIGINATOR "Fogra, www.fogra.org, developed by GMG
  GmbH & Co. KG, Heidelberger Druckmaschinen AG"`. Is this something Fogra can
  grant on its own, or would the consent of those companies also be needed?
* Is the answer different for a user's own downloaded copy — that is, may our
  software read a file the user fetched from you themselves, and compute a verdict
  from it?
* If including the files is **not** permitted, may we still (a) link to your
  download page from inside the application, so that a user fetches the file
  themselves, and (b) print the name "FOGRA51" in our report to identify which
  reference a measurement was judged against?

**If we do not hear from you.** We will read a silence as a no rather than as
permission: if we have had no reply by `<reply-by date>`, ChromIQ will ship with no
Fogra data in it, and we will not treat the absence of an answer as consent. We say
this only so that you know a non-answer costs us nothing improper, and that no
deadline is being placed on you.

Thank you for your time.

Yours sincerely,

`<name>`
ChromIQ
`<email>`
`<postal address, if you wish to give one>`
