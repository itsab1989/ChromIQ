<!-- ChromIQ / issue #182 — DRAFT, NOT SENT. Published for review only.
     Names and addresses of individuals are replaced with role placeholders here;
     they live in the working copies, which are not published. -->

# Letter 4 — to Idealliance

**Status: DRAFT. Nothing has been sent.** This is published so it can be corrected
before a human signs it. Placeholders in angle brackets are for the sender to fill in;
placeholders in square brackets are role names standing in for individuals.

---

Dear Idealliance,

I am writing about the licence wording that accompanies your reference ICC profiles on the
ICC Profile Registry. We would like to include those profiles in a free application, we
think your wording may not allow it, and we would rather ask you than assume either way.

**Who we are.** ChromIQ is a free desktop application for making ICC colour profiles for
printers. It is published as open source under the GNU General Public License, version 3,
at <https://github.com/itsab1989/ChromIQ>. It is not sold and there is no paid edition. It
produces a measurement report that tells a user how far a printed result is from the
colours that were intended, and we are adding the ability to judge that result against a
recognised reference printing condition. Its users are photographers, fine-art printers and
repro staff working on inkjet and toner devices.

**The wording in question.** The ICC Profile Registry page for `GRACoL2013_CRPC6` — and the
pages for the other registered Idealliance profiles — states:

> *"This profile is made available by IDEAlliance, with permission of X-Rite, Inc., and may
> be used, embedded, exchanged, and shared without restriction. It may not be altered, or
> sold without written permission of IDEAlliance."*

**What we would like to do.** Include those profiles unaltered inside ChromIQ, so that a
user can pick a reference printing condition without hunting for a file, and compute aim
colour values by running a device value through the profile.

**What we would be doing, act by act, because they are easy to blur.** (1) **Naming** the
profile in a report, to identify what a measurement was compared with — a trademark question,
below. (2) **Including a copy** of the profile, unaltered, inside the application — this is
what we are asking about. (3) **Applying it** — running a device value through it to obtain an
aim colour, and printing a pass or a fail against that aim. (4) **Altering** it — we are not
asking for this and would not do it. (5) **Claiming** a G7 or Idealliance qualification — we
are not asking for this and the software will not state or imply it.

**Why we are not simply doing it.** ChromIQ is distributed under the GNU General Public
License, version 3. Two consequences meet your wording:

* That licence expressly permits anyone who receives the software to charge for a copy of
  it. If a profile inside the software may not be sold, then either that person is
  breaking your condition, or we are distributing something we may not distribute.
* That licence also forbids us to impose further restrictions on the people who receive
  the software. We cannot accept "may not be sold" on their behalf and pass it down to
  them; we can only either have a permission that reaches them too, or not ship the file.

We are aware that there is an argument that a data file shipped beside a program is a
separate work rather than part of it, and that the two licences therefore never meet. **We
are not going to decide that for ourselves**, and we are certainly not going to decide it
in a way that happens to suit us. It is your grant, and how it is meant to work alongside a
free-software licence is yours to say.

**We have shipped none of it.** No released version of ChromIQ contains any Idealliance
profile, and none is in our source repository. Nothing here asks you to bless something
already done.

**Four questions.**

* Does *"may not be … sold"* prevent a person who charges for a copy of free software that
  contains the profile from doing so — or is it aimed at selling the profile itself as a
  product?
* If it is the latter: would you be willing to say so in a form we could rely on — for
  example, that the profile may be included in and distributed with software under any
  licence, including where a recipient charges for the copy, provided the profile itself is
  unaltered and is not sold as a product in its own right?
* Is computing colour values *through* a profile — running a device value through it to
  obtain an aim colour — a use of it, and not an alteration of it? We read your wording as
  yes, and would be grateful for confirmation rather than a ruling.
* The registry records the copyright in these profiles as X-Rite, Inc., and your grant as
  made *"with permission of X-Rite, Inc."* Can Idealliance answer the questions above on
  its own, or would X-Rite's consent also be needed?

**A separate question about the names, which is not a copyright question.** "G7",
"GRACoL", "SWOP" and "Idealliance" are marks as well as words. We are not seeking any G7 or
Idealliance certification, qualification or approval, we are not asking to use your marks
as marks, and our software will not state that any print "conforms to", "is certified to"
or "qualifies as" anything. What it would do is print a profile's own name — for example
`GRACoL2013_CRPC6` — solely to identify what a measurement was compared with. Is that
acceptable to you? We ask separately because it is a trademark question and not a copyright
one, and because the answer may differ.

**The attribution we would propose.** So that you do not have to invent wording for us:

> *Reference profile: GRACoL2013_CRPC6, made available by Idealliance with the permission
> of X-Rite, Inc., included unaltered. Idealliance does not endorse, certify or approve this
> software or any result it produces. No G7 or Idealliance qualification is claimed.*

**If we do not hear from you.** We will read a silence as a no rather than as permission:
if we have had no reply by `<reply-by date>`, ChromIQ will ship with no Idealliance profile
in it and will link to the ICC registry instead. We say this only so that you know a
non-answer costs us nothing improper, and that no deadline is being placed on you.

Thank you for your time.

Sincerely,

`<name>`
ChromIQ
`<email>`
`<postal address>`
