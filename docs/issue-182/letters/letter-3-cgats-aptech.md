<!-- ChromIQ / issue #182 — DRAFT, NOT SENT. Published for review only.
     Names and addresses of individuals are replaced with role placeholders here;
     they live in the working copies, which are not published. -->

# Letter 3 — to the CGATS Secretariat at APTech

**Status: DRAFT. Nothing has been sent.** This is published so it can be corrected
before a human signs it. Placeholders in angle brackets are for the sender to fill in;
placeholders in square brackets are role names standing in for individuals.

---

Dear CGATS Secretariat,

I am writing to ask about the terms on which two things CGATS publishes may be used
in free software. If either use is not permitted, a plain no is as useful to us as a
yes, and we would rather have it than keep inferring one.

**Who we are.** ChromIQ is a free desktop application for making ICC colour profiles
for printers. It is published as open source under the GNU General Public License,
version 3, at <https://github.com/itsab1989/ChromIQ>. It is not sold and there is no
paid edition. It produces a measurement report that tells a user how far a printed
result is from the colours that were intended, and we are adding the ability to judge
that result against a recognised reference printing condition rather than only against
the chart's own design values. Its users are photographers, fine-art printers and
repro staff working on inkjet and toner devices.

**First: the characterization data.** The CGATS21-2 Characterized Reference Printing
Condition data sets (CRPC 1–7) reach a user from three places we can find, and none of
the three states any terms:

* your own site, `printtechnologies.org/standards/characterization-data-sets`, which
  serves `cgats21-2-crpc1..7.txt` and the `ISO15339-CRPC1..7.txt` files directly;
* the ICC Profile Registry at `registry.color.org`, where the same data is linked as
  "Target data" from each registered profile and each file carries
  `ORIGINATOR "CGATS"`;
* `standards.iso.org`, as the electronic inserts to ISO/PAS 15339-2.

We would like to include those files **unaltered** inside our application, so that a
user can select, for example, "CRPC6" as the reference for a verification without
first having to find and download the file. We would name CGATS as the source wherever
the data is used. If that is not permitted, we will link to your published files
instead and have each user download their own copy — which is what we do today.

**What we would be doing with the data, stated in full.** There are five acts here and
they are easy to blur, so all five:

1. **Naming the data set** in a report, to identify what a measurement was compared
   with. We assume this needs nothing from you; if that assumption is wrong, that is
   the most important thing you could tell us.
2. **Reading a copy the user downloaded themselves** from one of the three sites
   above. We assume this is what a free download is for.
3. **Including a copy inside our application** — that is, redistributing your file to
   our users. **This is what we are asking permission for.**
4. **Applying the data — computing a verdict from it.** Our software would not only
   show your values; it would subtract a user's measurement from them and print a pass
   or a fail. We state it separately because it is a different act from display, and
   we would rather you judged the real one.
5. **Claiming any CGATS, G7, GRACoL, SWOP or Idealliance certification,
   qualification or approval.** We are not asking for this and the software will not
   state or imply it. Where a reference condition is named, the wording would be
   *"compared against the CGATS21-2 CRPC6 data set"*, and nothing more.

**One thing about our licence, because it shapes what a permission would have to say.**
ChromIQ is distributed under the GNU General Public License, version 3. That licence
requires that everyone who receives the software receives the same rights we have, and
it does not allow us to pass on to them a restriction we accepted ourselves. So a
permission granted to us alone — to "ChromIQ", or to its authors — would be of no
practical use: the first person to redistribute the software, which the licence permits
anyone to do, would fall outside it, and we would have to remove the files again. What
would work is a permission that travels with the files to everyone who receives the
software. The same point may apply to any condition of the form "may not be sold":
GPLv3 expressly permits a recipient to charge for a copy. Whether that actually
conflicts depends on whether a data file shipped beside a program is part of it or
merely aggregated with it, and that is not a question we are going to answer in our own
favour — so if you are minded to attach such a condition, it is worth telling us,
because it may make the permission unusable.

**We have shipped none of it.** No released version of ChromIQ contains any CGATS data,
and none is in our source repository. Nothing here asks you to bless something already
done.

**Second: TR 015-2022, and a reading we would like confirmed rather than corrected.**
The copyright block at the foot of page ii reads:

> *"©2022 APTech The Association for PRINT Technologies. All rights reserved.*
>
> *The data and formulae in this document are free for anyone to use.. Any reproduction
> or use in any form requires prior written permission from APTech. Requests for such
> permission should be addressed in writing to the CGATS Secretariat, APTech, at the
> address shown on the cover."*

We have read the whole of page ii, not only that block: it also records that the document
is *"not an American National Standard and the material contained herein is informative in
nature"*, and it gives a separate route — *"Questions and comments regarding this Technical
Report should be addressed to the CGATS Secretariat"* — which is not the route we are using,
because this is a permission question rather than a comment on the report.

We read the copyright block as saying two different things about two different objects: that the
**data and the formulae** the document defines are free for anyone to use, including in
software; and that the **document itself** — its text, its tables, its figures — may not
be reproduced or otherwise used without your written permission. On that reading, our
implementing the aim formulae in software needs nothing from you, and reproducing pages
of TR 015 would.

**Is that reading right?** If it is, this half of the letter is closed with one word and
we will not trouble you again about it. If it is not — if the second sentence is meant
to govern the formulae as well — then this letter is the written request the page calls
for, and we would be asking to implement the NPDC and grey-balance aim formulae in
software, computing values with them, and not to reproduce the text or the tables of the
report.

**The attribution we would propose.** So that you do not have to invent wording for us,
here is what we would display, and we would of course use yours instead if you prefer:

> *Reference data: CGATS21-2 CRPC6, published by CGATS / the Association for Print
> Technologies, included with permission and unaltered. Aim formulae after
> CGATS/Idealliance TR 015-2022. Neither CGATS nor APTech endorses, certifies or
> approves this software or any result it produces.*

We have written it as "published by" rather than "©" because we do not know who holds
the copyright in the data, and would rather you told us than guess.

**A separate question about the names, which is not a copyright question.**
"CGATS21-2", "CRPC6" and "G7" are names as well as things, and names can be protected in
ways that measured numbers are not. Quite apart from everything above: is it acceptable
to you that ChromIQ prints such a name in a report solely to identify what a measurement
was compared with, or which formulae were used? We would use them as plain identifiers
and never as marks of approval. We ask separately because a "no" on the data need not be
a "no" on the name, and the second answer decides whether a reduced version of this
feature can exist at all. We understand that G7 in particular is a mark you protect, and
we would rather be told the rule than discover it.

**What would help us most.** Even a short answer to just the first question — may the
CRPC data files be included unaltered in a free application, yes or no — would settle
the design of a feature that is otherwise held up on an inference.

**If we do not hear from you.** We will read a silence as a no rather than as
permission: if we have had no reply by `<reply-by date>`, ChromIQ will ship with no CGATS
data in it and will link to your published files instead. We say this only so that you
know a non-answer costs us nothing improper, and that no deadline is being placed on you.

Thank you for your time.

Sincerely,

`<name>`
ChromIQ
`<email>`
`<postal address>`
