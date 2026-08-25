# Ανέβασμα online (Render.com, δωρεάν)

Θα χρειαστείς δύο δωρεάν λογαριασμούς: GitHub και Render. Στο τέλος θα έχεις
έναν σύνδεσμο (π.χ. `https://oikismoi-elstat.onrender.com`) που μπορεί να
ανοίξει ο καθένας, χωρίς να εγκαταστήσει τίποτα.

## Βήμα 1 — Λογαριασμός στο GitHub

1. Πήγαινε στο https://github.com και κάνε **Sign up** (αν δεν έχεις ήδη).

## Βήμα 2 — Δημιούργησε ένα repository με τον κώδικα

1. Στο GitHub, πάτα το **+** πάνω δεξιά → **New repository**.
2. Δώσε ένα όνομα, π.χ. `oikismoi-elstat`. Άσε το **Public**. Μην τσεκάρεις
   τίποτα άλλο (χωρίς README, χωρίς .gitignore — τα έχουμε ήδη).
3. Πάτα **Create repository**.
4. Στη σελίδα που ανοίγει, πάτα τον σύνδεσμο **uploading an existing file**.
5. Σύρε μέσα **όλα** τα αρχεία και φακέλους από τον φάκελο `elstat` που έχεις
   ήδη στον υπολογιστή σου (`app.py`, `build_db.py`, `requirements.txt`,
   `Procfile`, `.gitignore`, `README.md`, `DEPLOY.md`, και ολόκληρο τον
   φάκελο `static/`). **Μην** ανεβάσεις τους φακέλους `data/` ή το αρχείο
   `settlements.db` αν υπάρχουν τοπικά — δεν χρειάζονται, θα φτιαχτούν στον
   server.
6. Κάτω-κάτω πάτα **Commit changes**.

## Βήμα 3 — Λογαριασμός στο Render

1. Πήγαινε στο https://render.com και κάνε **Sign up** — πιο εύκολο με
   **Sign up with GitHub**, γιατί συνδέει αυτόματα τον λογαριασμό σου.

## Βήμα 4 — Δημιούργησε το Web Service

1. Στο Render dashboard, πάτα **New +** → **Web Service**.
2. Επίλεξε **Build and deploy from a Git repository** και σύνδεσε το
   repository `oikismoi-elstat` που έφτιαξες.
3. Συμπλήρωσε:
   - **Name**: ό,τι θέλεις (θα γίνει μέρος του συνδέσμου)
   - **Region**: Frankfurt (πιο κοντά στην Ελλάδα)
   - **Branch**: main
   - **Runtime**: Python 3
   - **Build Command**:
     ```
     pip install -r requirements.txt && python build_db.py
     ```
   - **Start Command**:
     ```
     gunicorn app:app
     ```
   - **Instance Type**: Free
4. Πάτα **Create Web Service**.

## Βήμα 5 — Περίμενε το deploy

Το Render θα εγκαταστήσει τις βιβλιοθήκες, θα κατεβάσει τα 3 αρχεία της
ΕΛΣΤΑΤ και θα χτίσει τη βάση — το βλέπεις live στα logs. Παίρνει μερικά
λεπτά την πρώτη φορά. Όταν τελειώσει, στο πάνω μέρος της σελίδας θα δεις
τον σύνδεσμο της εφαρμογής σου (κάτι σαν
`https://oikismoi-elstat.onrender.com`).

Αυτόν τον σύνδεσμο τον στέλνεις σε όποιον θέλεις — ανοίγει κατευθείαν στον
browser του, χωρίς καμία εγκατάσταση.

## Πρακτικά για το δωρεάν tier

- Αν δεν έχει χρήση για ~15 λεπτά, ο server "κοιμάται" και το επόμενο άνοιγμα
  αργεί λίγα δευτερόλεπτα να ξυπνήσει. Απόλυτα φυσιολογικό.
- Αν χρειαστεί ποτέ να ξαναφτιάξεις τη βάση από την αρχή (π.χ. η ΕΛΣΤΑΤ
  ενημέρωσε τα αρχεία), πήγαινε στο Render → το service σου → **Manual
  Deploy** → **Clear build cache & deploy**.
- Κάθε αλλαγή που κάνεις στον κώδικα στο GitHub (π.χ. επεξεργασία αρχείου
  online) πυροδοτεί αυτόματα νέο deploy.
