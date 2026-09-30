# MANA DID: Sovereign Passport — Privacy Policy

**Status: DRAFT — not yet reviewed by a lawyer.** This is a first pass based on
what the code actually does today. Before this is used with real users, it
should be reviewed by a lawyer familiar with the Privacy Act 2020 (and GDPR,
if EU users are ever in scope), and updated to match.

*Last updated: [DATE]*

---

## 1. What we collect

When you use MANA DID to verify and register your identity, we collect:

- **Your full name**, as you type it into the registration form.
- **A photo of your ID document**, which you upload to prove your name
  matches a real document.
- **Your wallet address**, from the wallet you connect (e.g. MetaMask).

## 2. What we do with your ID photo

Your ID photo is used **only** to extract text from it, using OCR
(optical character recognition), so we can confirm the name you typed
matches the name on your document.

**Your ID photo is never saved, stored, or retained.** It exists only in
your device's request to our server and in our server's temporary memory
for the few seconds it takes to process. Once the OCR check is complete,
the photo is discarded — it is never written to disk, never logged, and
never stored in any database.

## 3. What we do with your name

If your typed name matches the name found on your ID photo, we store your
name — **encrypted** — linked to your wallet address. This lets our
service confirm "this wallet belongs to this name" later, without your
name being visible on the public blockchain.

- Your name is encrypted using a standard, industry-recognized encryption
  method (Fernet/AES) before being stored.
- The encryption key is kept separately and securely (in your device's
  or our server's secure credential storage), not alongside the stored
  data itself.
- Your name is **not** stored on the blockchain. Only a scrambled
  (hashed and salted) version of it is stored on-chain, which cannot be
  reversed to recover your actual name.

## 4. What's stored on the blockchain (public, permanent)

Because blockchains are public and permanent by design, the following
information is visible to anyone, forever, and **cannot be deleted or
changed** once submitted:

- Your wallet address.
- A scrambled (hashed) version of your name, combined with your wallet
  address, so it cannot be looked up or guessed in bulk.
- The expiry date of your registered identity.
- Which other wallet addresses you have granted permission to view your
  registered name.

**Nobody can read your actual name from the blockchain alone** — the
on-chain data only lets someone confirm a name against what you already
told them, not discover it independently.

## 5. Who can see your name

- **You** always have access to your own information.
- **Anyone you explicitly grant access to**, via the `grant_access`
  function, which requires a transaction signed by your own wallet. You
  can revoke this access at any time.
- **The service operator** (us) can technically decrypt and view stored
  names, since we hold the means to operate the encryption/decryption
  process. We do not access this data except as needed to operate and
  maintain the service, or as required by law.

## 6. How long we keep your data

Your name is stored off-chain, encrypted at rest, only so that it can be shown to people you have granted access to. We do not keep it longer than your registration is valid.

**Automatic deletion.** Each time our server starts, it checks the blockchain for every stored identity. If an identity's on-chain registration has expired, or was never completed on-chain, the stored name is permanently deleted from our database. A deleted name cannot be recovered, and you would need to verify and register again to restore access. If the blockchain cannot be reached during a check, nothing is deleted for that identity until the next check.

**Timing.** Deletion happens when the server starts, not at the exact moment a registration expires, so an expired name may remain stored until the next check runs.

**What is not deleted.** Your registration on the blockchain (a salted hash of your name and your expiry date) is stored on a public blockchain and cannot be deleted by us. It is not linked to your name once your stored name has been removed.

**Votes.** Votes cast in the mock election are stored separately and are not affected by identity deletion.
## 7. Your rights

Depending on where you live, you may have rights to access, correct, or
request deletion of your personal information. Because on-chain data is
permanent by the nature of blockchain technology, deletion requests can
only apply to the encrypted name we hold off-chain — **not** to
information already recorded on the blockchain.

To make a request, contact: **[YOUR CONTACT EMAIL]**

## 8. Security

We take reasonable steps to protect your information, including
encrypting your name at rest and keeping the encryption key separate
from the encrypted data. However, no system is completely secure, and
we cannot guarantee absolute security.

## 9. Changes to this policy

We may update this policy as the service develops. Material changes
will be noted here with an updated date.

## 10. Contact

Questions about this policy or your data can be directed to:
**[YOUR CONTACT EMAIL]**

---

*This document is a draft prepared with AI assistance based on a review
of the application's source code as of [DATE]. It has not been reviewed
by a lawyer and should not be relied upon as legal advice or as a
compliant policy until reviewed by a qualified professional familiar
with the Privacy Act 2020 and any other applicable law.*
