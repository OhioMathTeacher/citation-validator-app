# Deployment Guide: Citation Validator Web App

## 🚀 Quick Deployment Options

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
