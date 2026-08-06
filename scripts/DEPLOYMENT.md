# Deployment Guide: Citation Validator Web App

## The live deployment: Hugging Face Spaces

**This is the one that is actually running.** The public demo the papers and the
Code4Lib proposal link to is <https://huggingface.co/spaces/ojsm/citation-validator>.
Everything below this section is an alternative that has been tried or could be
used; none of it is what serves the live app.

### It is a separate repository

The Space is its own git repo. **Pushing this repository to GitHub does not
update it.**

```bash
# Clone once, alongside this repo
git clone git@hf.co:spaces/ojsm/citation-validator ~/Repos/citation-validator-space
```

| | Repository |
|---|---|
| Development | `github.com/OhioMathTeacher/citation-validator-app` |
| Live Space | `hf.co:spaces/ojsm/citation-validator` (local clone: `~/Repos/citation-validator-space`) |

That separation is the single most important fact here. On 2026-08-05 the Space
was found running a full version behind — it still had author-matching defects
the paper describes fixing, including a crash on non-Latin author names —
because everyone assumed a GitHub push deployed it.

### How to sync a change

Copy only the files that changed, commit in the Space repo, push:

```bash
cd ~/Repos/citation-validator-space
cp ~/Repos/citation-validator-app/scripts/citation_validator.py    scripts/
cp ~/Repos/citation-validator-app/scripts/citation_enhancements.py scripts/
git add scripts/ && git commit -m "Sync <what> to the Space" && git push origin main
```

**Never copy these from the app repo:**

| File | Why |
|---|---|
| `README.md` | Carries the Space's YAML frontmatter — the SDK, port and title Hugging Face reads. Overwriting it put the Space in `CONFIG_ERROR` for ~12 minutes on 2026-08-05. |
| `Dockerfile` | The Space's build differs from local. |
| `datasets/manifest.json` | The Space ships without the gitignored third-party data; see `datasets/README.md`. |

Before pushing, confirm nothing else drifted:

```bash
cd ~/Repos/citation-validator-space
for f in $(git ls-files scripts/ web/ | grep -v __pycache__); do
  diff -q "$f" "$HOME/Repos/citation-validator-app/$f" >/dev/null 2>&1 || echo "DIFFERS: $f"
done
```

### Confirm it came back up

A push triggers a rebuild. It is not deployed until the stage reads `RUNNING` —
`BUILD_ERROR`, `RUNTIME_ERROR` and `CONFIG_ERROR` are all silent in the git
output, so check explicitly rather than assuming the push was the last step:

```bash
curl -s https://huggingface.co/api/spaces/ojsm/citation-validator \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['runtime']['stage'])"
```

Expect `RUNNING_BUILDING` → `RUNNING_APP_STARTING` → `RUNNING`, usually under
two minutes. If it stops at `CONFIG_ERROR`, `README.md` is the first thing to
check.

### Rolling back

The Space is a normal git repo, so a bad deploy reverts like any other:

```bash
cd ~/Repos/citation-validator-space
git revert <sha> && git push origin main   # then re-check the stage above
```

---

## 🚀 Other deployment options

*The following are alternatives, not the live deployment. See above.*

### Option 1: Heroku (Easiest - Free Tier)

**Prerequisites:** 
- Free Heroku account at https://heroku.com
- Heroku CLI installed: `brew install heroku` (Mac) or download from heroku.com

**Steps:**

```bash
# 1. Navigate to scripts directory
cd /path/to/Ohio-Journal-of-School-Mathematics/scripts/

# 2. Create Procfile
echo "web: python webapp.py" > Procfile

# 3. Initialize git (if not already)
git init

# 4. Create Heroku app
heroku create citation-validator-ojsm

# 5. Deploy
git push heroku main

# 6. Open in browser
heroku open
```

**Your app will be live at:** `https://citation-validator-ojsm.herokuapp.com`

---

### Option 2: PythonAnywhere (Free Tier - No Credit Card!)

**Prerequisites:**
- Free account at https://pythonanywhere.com

**Steps:**

1. **Sign up** at PythonAnywhere (free tier, no credit card)
2. **Open a Bash console** from dashboard
3. **Clone repository:**
   ```bash
   git clone https://github.com/OhioMathTeacher/Ohio-Journal-of-School-Mathematics.git
   cd Ohio-Journal-of-School-Mathematics/scripts
   ```
4. **Install Flask:**
   ```bash
   pip install --user Flask
   ```
5. **Go to Web tab** → Add new web app
6. **Select Flask** → Python 3.8+
7. **Set paths:**
   - Source code: `/home/YOUR_USERNAME/Ohio-Journal-of-School-Mathematics/scripts`
   - WSGI file: Edit to point to `webapp.py`
8. **Reload web app**

**Your app will be live at:** `https://YOUR_USERNAME.pythonanywhere.com`

---

### Option 3: Vercel (Free - Automatic Deploys)

**Prerequisites:**
- Free Vercel account at https://vercel.com
- Vercel CLI: `npm install -g vercel`

**Steps:**

```bash
# 1. Navigate to scripts directory
cd scripts/

# 2. Create vercel.json
cat > vercel.json << 'EOF'
{
  "version": 2,
  "builds": [
    {
      "src": "webapp.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "webapp.py"
    }
  ]
}
EOF

# 3. Deploy
vercel

# 4. Follow prompts, then:
vercel --prod
```

**Your app will be live at:** `https://citation-validator.vercel.app`

---

### Option 4: Run Locally (Great for Testing)

```bash
# 1. Install Flask
pip install Flask

# 2. Run server
cd scripts/
python3 webapp.py

# 3. Open browser to:
http://localhost:5000
```

**Share on local network:**
```bash
# Find your IP address
# Mac/Linux: ifconfig | grep "inet "
# Windows: ipconfig

# Run server accessible to network
python3 webapp.py

# Others on same WiFi can access:
http://YOUR_IP_ADDRESS:5000
```

---

## 📦 What Gets Deployed

The web app includes:
- ✅ Full HTML/CSS/JavaScript interface (embedded in `webapp.py`)
- ✅ Citation validation engine
- ✅ CrossRef & OpenAlex API integration
- ✅ Optional Groq AI analysis
- ✅ Export functionality (HTML, JSON, CSV)
- ✅ No database needed (stateless)

---

## 🔐 Security Notes

**API Keys:**
- Stored only in user's browser (localStorage)
- Never sent to your server
- Used only for direct Groq API calls from browser

**For production:**
- Add rate limiting if expecting high traffic
- Consider adding CORS headers if needed
- Use HTTPS (automatic on Heroku/Vercel/PythonAnywhere)

---

## 🌐 Share Your Deployment

Once deployed, share with:
- **Nature authors:** Include in correspondence about hallucinated citations
- **Journal editors:** Tool for manuscript screening
- **Reviewers:** Quick citation validation during peer review
- **Publishers:** Batch processing for quality control

---

## 💡 Tips

**Custom domain:**
- Heroku: Add custom domain in app settings ($7/month for SSL)
- Vercel: Free custom domains with automatic SSL
- PythonAnywhere: Paid tiers support custom domains

**Analytics:**
- Add Google Analytics snippet to track usage
- Monitor which features are most used

**Branding:**
- Edit the HTML template to customize colors, logo
- Add your institution's branding

---

## 🆘 Troubleshooting

**"Application Error":**
- Check logs: `heroku logs --tail` (Heroku)
- Ensure Flask is listed in `requirements.txt`
- Verify Python version compatibility

**"502 Bad Gateway":**
- Increase timeout settings in deployment platform
- Check if APIs (CrossRef, OpenAlex) are accessible

**API key not saving:**
- Check browser localStorage is enabled
- Try different browser
- Check browser console for errors (F12)

---

## 📊 Monitoring

**Free monitoring tools:**
- UptimeRobot: Monitor if site is up (free)
- Google Search Console: Track SEO
- Plausible Analytics: Privacy-friendly alternative to Google Analytics

**Check API usage:**
- Groq console: Track API calls (users' keys, not yours)
- Rate limiting: Add if needed

---

## 🎯 Next Steps

After deployment:
1. Test with sample .bib file
2. Share URL with colleagues
3. Post on Twitter/LinkedIn announcing free tool
4. Submit to Nature as supplementary tool
5. Add to academic tool directories

**Need help?** Open an issue on GitHub!
