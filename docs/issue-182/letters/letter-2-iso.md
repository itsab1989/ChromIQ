<!-- ChromIQ / issue #182 — DRAFT, NOT SENT. Published for review only.
     Names and addresses of individuals are replaced with role placeholders here;
     they live in the working copies, which are not published. -->

# Letter 2 — to ISO

**Status: DRAFT. Nothing has been sent.** This is published so it can be corrected
before a human signs it. Placeholders in angle brackets are for the sender to fill in;
placeholders in square brackets are role names standing in for individuals.

---

Dear ISO Copyright Office,

I am writing to ask for permission for a specific and narrow use of two of your
standards. If the answer is no, a plain no is genuinely useful to us, and we would
rather have it than keep inferring one.

**Who we are.** ChromIQ is a free desktop application for making ICC colour
profiles for printers. It is published as open source under the GNU General Public
License, version 3, at <https://github.com/itsab1989/ChromIQ>. It is not sold and
there is no paid edition. It drives the open-source ArgyllCMS colour tools and
produces a measurement report which tells a user how far a printed result is from
the colours that were intended. Its users are photographers, fine-art printers and
repro staff working on inkjet and toner devices.

**What we would like to do.** ChromIQ currently judges a printed result against a
single pair of pass/fail limits that we chose ourselves. Our users, who work in
print, have asked us instead to offer the limits that the recognised standards set,
so that a report can say which limits it was judged against.

Concretely, we would like to store, inside the software, the **numerical tolerance
values** given in the tables of **ISO 12647-8:2021** as the factory default pass/fail
limits of a named setting; to display those numbers on
screen and in the report; and to **compute a verdict from them** — that is, to
subtract a measurement from a value, compare the difference with the tolerance, and
print a pass or a fail. Each value would be shown together with the designation of
the standard and the number of the clause and table it comes from, so that its
origin is stated rather than absorbed. The user can edit any of them.

**What we are asking about, and what we are not.** It matters to us that these are
kept apart, so I will state all five:

1. **Citing a clause.** Naming a standard and a clause number in help text — for
   example, "the tolerance for the substrate is set in ISO 12647-8:2021, clause
   4.2". We understand from your own guidance that citing is encouraged, and we are
   not asking for it.
2. **Displaying the numbers.** Storing the tolerance values as editable defaults and
   showing them in the interface and in the report, each attributed to its clause.
   **This is part of what we are asking permission for.**
3. **Applying the numbers.** Computing a pass or fail from them and printing that
   verdict. **This is the other part, and it is the one the software actually
   does.** We state it separately because it is a different act from display, and
   because we would rather you judged the real one: the numbers are not decoration
   in our software, they are the rule the software applies.
4. **Redistributing a document or a dataset.** We are **not** asking to reproduce,
   quote or distribute the text of either standard, in whole or in part, and the
   software would contain no copy of either document. Nor would it offer any means
   of copying or exporting the tolerance tables as a block: no "copy all", no export
   of the table, and no file in the installation holding the tables in a form that
   could simply be lifted out.
5. **Claiming conformance.** We are **not** asking to certify anything, and the
   software will not say that any print "conforms to" or "is certified to" either
   standard. Its wording would be of the form *"measured against the tolerance
   values of ISO 12647-8:2021, Table N"*. Conformity assessment is not ours to
   assert and we do not intend to imply it. We would add, in the report itself,
   which requirements of the standard our software does **not** evaluate, so that a
   reader cannot mistake a colour check for a conformity statement.

**One thing about our licence, because it shapes what a permission would have to
say.** ChromIQ is distributed under the GNU General Public License, version 3. That
licence requires that everyone who receives the software receives the same rights we
have, and it does not allow us to pass on to them a restriction we accepted
ourselves. A permission granted to us alone — to "ChromIQ", or to its authors —
would therefore be of no practical use: the first person to redistribute the
software, which the licence permits anyone to do, would fall outside it. What we
would need is a permission that travels with the software to everyone who receives
it. If that is more than ISO is willing to grant, knowing so is still worth the
letter, because it decides between two quite different designs rather than between
a feature and nothing.

**We have shipped none of it.** No released version of ChromIQ contains any value
taken from either standard, and none is in our source repository. Nothing here asks
you to bless something already done.

**How we have read the standards so far, stated plainly.** We do **not** hold a
licensed copy of either document. What we have worked from is extracts that
circulate freely on the internet and third-party summaries of the tables. We are
telling you this rather than letting you assume otherwise, because it bears on your
answer: if the honest first step is to buy both standards under an ordinary licence,
we will do that. It is also why the second question below matters to us.

**Why we are asking rather than assuming.** We have read your Copyright page, your
Terms and Conditions and End Customer Licence Agreement, and the guide *How to best
use IEC and ISO standards*. Two passages seem to bear on this, and we quote both in
full rather than in part, because a half quotation of either would mislead.

Section 4 of the Licence Agreement, on what a purchased licence includes:

> *"Permitted use includes the right to access, read, consult, and internally
> reference the ISO Publication, as well as to understand, evaluate, and apply its
> content within the Licensee's internal operations, internal processes, internal
> management systems, internal products, and internal services.*
>
> *Except where expressly authorized under additional licences, as set out in
> Sections 6 and 7, this Licence does not include rights of reproduction,
> distribution, adaptation, incorporation, digital integration, or creation of
> derivative works of the ISO Publication, in whole or in part."*

Section 6 b), on acts requiring an additional licence:

> *"Any of the following acts require an additional licence from ISO, an ISO Member
> Body, or an authorized distributor: … b) Digital integration or incorporation of
> ISO Publications — Any integration, embedding, encoding, structuring,
> transformation, or operationalization of the ISO Publication within any digital or
> software-based environment, including but not limited to: software applications or
> workflow tools; rules engines, compliance systems, or automated decision-making
> tools; databases, data models, or structured datasets; automated or AI-enabled
> tools; digital platforms or services; any similar digital solution used internally
> or made available to third parties."*

**We are not in a position to say which of those governs what we want to do, and we
are not going to decide it for you.** Section 4 permits a licensee to *apply* the
content within their own products and services; Section 6 b) reserves *integration
into a software-based environment*. A handful of tolerance values used as the
pass/fail rule of a free application, each attributed to its clause, could plausibly
be read either way, and the reading is yours to give, not ours to assume. That
question is the reason for this letter.

The guide, under the heading *"Copy parts of a standard for your book or software"*,
says: *"Citing standards or including extracts of standards is encouraged as long as
there is the correct acknowledgement and the conditions of your licence are
respected. Please contact IEC or ISO for authorization."* This letter is that
contact.

**The attribution we would propose.** So that you do not have to invent wording for
us, here is what we would display next to the values, and we would of course use
yours instead if you prefer:

> *Tolerance values from ISO 12647-8:2021, Table N, reproduced with the permission
> of ISO. ISO retains all rights in the standard. This software is not published,
> endorsed, approved or certified by ISO, and no conformity to ISO 12647-8:2021 is
> claimed. The complete standard is available from ISO at www.iso.org and from ISO's
> national member bodies.*

**A separate question about the designations, which is not a copyright question.**
"ISO 12647-8" is a designation as well as a document, and designations can be
protected in ways that numbers in a table are not. Quite apart from everything
above: is it acceptable to you that ChromIQ prints the designation of a standard in
its report solely to identify what a measurement was compared with? We would use it
as a plain identifier and never as a mark of approval. We ask separately because a
"no" on the values need not be a "no" on the designation, and that second answer
decides whether a reduced version of this feature can exist at all.

**This request is about ISO 12647-8:2021 only, and that is deliberate.** An earlier
draft of this letter asked about ISO 12647-7:2016 as well, as an equal. It should not
have, for two reasons.

The first is that -8 is the document our users need. They print from digital data on
inkjet and toner devices, which is to say they make validation and design prints — what
-8 addresses. ISO 12647-7:2016 governs contract proofing, which far fewer of them do.

The second is that we could not use a permission for -7 today even if you granted it.
Of the twelve requirements of ISO 12647-7:2016 we have been able to identify, **ten are
things our software cannot evaluate at all** — substrate gloss class, substrate
fluorescence class, within-format uniformity over nine locations, permanence under four
storage regimes, rub resistance, and so on: we have no gloss input, no fluorescence
input, no nine-location workflow and no permanence test. An eleventh we can do only in
part. It would be wrong to ask you for something we cannot yet use, and it would be
worse than wrong tactically: a single refusal covering both documents would take the one
we can use down with the one we cannot.

So: **ISO 12647-8:2021 now.** If ChromIQ ever grows the measurements that -7 requires,
we will write again about -7, separately, and that letter will be able to say what the
software actually does with it.

**Four practical questions, so that we can act on your answer.**

* If this use is permitted, on what terms — is there a fee, and can the permission
  be one that travels with the software to everyone who receives it, as described
  above?
* Is holding a purchased copy of the standard a precondition for even asking? We are
  willing to buy it, and would rather know before we do whether that purchase would or
  would not by itself cover the use described here — Section 4 suggests to us that it
  would not, but that is exactly the sort of thing we should not be deciding for
  ourselves.
* Should this go to you at all, or to the ISO member body in the sender's country?
  Your Copyright page offers both routes, and Section 6 b) names a member body and
  an authorized distributor alongside ISO. If we have come to the wrong door, please
  say which is the right one.
* If it is not permitted, may we still name the standard and its clause numbers in the
  software's help text and report, while leaving the user to enter the values themselves
  from their own licensed copy?

A short answer to that last question is genuinely useful to us even if everything
else is a no, because it decides whether the feature exists in a reduced form or not
at all.

**If we do not hear from you.** We will read a silence as a no rather than as
permission: if we have had no reply by `<reply-by date>`, ChromIQ will ship with no
value from the standard in it, and we will not treat the absence of an answer as
consent. We say this only so that you know a non-answer costs us nothing improper,
and that no deadline is being placed on you.

Thank you for your time.

Yours faithfully,

`<name>`
ChromIQ
`<email>`
`<postal address, if you wish to give one>`
