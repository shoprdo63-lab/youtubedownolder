# YouTube Downloader Pro

> הכלי המהיר, הבטוח והחינמי ביותר להורדת סרטוני YouTube בכל האיכויות

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/flask-3.0+-green.svg" alt="Flask 3.0+">
  <img src="https://img.shields.io/badge/yt--dlp-latest-red.svg" alt="yt-dlp">
  <img src="https://img.shields.io/badge/license-MIT-orange.svg" alt="License MIT">
</p>

## ✨ תכונות עיקריות

| תכונה | פרטים |
|-------|-------|
| 🎬 **איכויות וידאו** | 144p עד 4320p (8K) – כל האיכויות הזמינות ב-YouTube |
| 🎵 **הורדת אודיו** | MP3 באיכות 320kbps – הפרדה מלאה מווידאו |
| 🖼️ **תצוגה מקדימה** | תמונה ממוזערת, כותרת, משך ושם הערוץ |
| ⚡ **מהיר וחינמי** | אין הרשמה, אין מגבלות, אין פרסומות |
| 🔒 **בטוח לחלוטין** | פועל מהדפדפן – ללא התקנות |
| 📱 **רספונסיבי** | תמיכה מלאה במחשב, טאבלט ונייד |
| 🌐 **בלוג מקצועי** | מדריכים, טיפים ומידע SEO-friendly |

## 🚀 התקנה והרצה

### דרישות מקדימות
- Python 3.8+
- FFmpeg (נדרש להמרת אודיו ל-MP3)

### שלב 1: התקנת תלותיות

```bash
pip install -r requirements.txt
```

### שלב 2: הפעלת השרת

```bash
python app.py
```

האתר יהיה זמין בכתובת: **http://localhost:5000**

## 📖 איך משתמשים

1. **הדבק קישור** – העתק כל קישור YouTube (סרטון רגיל, Shorts, או פלייליסט)
2. **לחץ "חפש סרטון"** – המערכת תביא מידע על כל הפורמטים הזמינים
3. **בחר איכות** – בחר בין וידאו (MP4) או אודיו בלבד (MP3)
4. **לחץ "הורד"** – הקובץ יורד אוטומטית לתיקיית ההורדות

## 🏗️ מבנה הפרויקט

```
youtube-downolder/
├── app.py                    # שרת Flask הראשי
├── requirements.txt          # תלותי Python
├── README.md                 # קובץ זה
├── .gitignore               # קבצים להתעלמות
├── static/
│   ├── css/
│   │   └── style.css        # עיצוב מקצועי – dark mode
│   └── js/
│       └── app.js           # לוגיקת הורדה בצד לקוח
└── templates/
    ├── base.html            # תבנית בסיס עם SEO
    ├── index.html           # דף הבית – כלי ההורדה
    └── blog.html            # בלוג מקצועי
```

## 🔧 טכנולוגיות

- **Backend:** Flask, yt-dlp
- **Frontend:** HTML5, CSS3 (Custom Properties), Vanilla JS
- **Design:** Dark theme, Glassmorphism, CSS Grid
- **SEO:** Open Graph, Twitter Cards, Schema.org

## 🛡️ בטיחות

- אין צורך בהתקנת תוכנות חיצוניות
- אין איסוף מידע אישי
- כל ההורדות מתבצעות ישירות מהדפדפן
- קוד פתוח – ניתן לבדיקה וביקורת

## 📋 רשימת איכויות נתמכות

| איכות | רזולוציה | מתאים ל... |
|-------|----------|-----------|
| 144p | 256×144 | חיבור איטי |
| 360p | 480×360 | נייד |
| 480p | 854×480 | טאבלט |
| 720p | 1280×720 | HD סטנדרטי |
| 1080p | 1920×1080 | Full HD |
| 1440p | 2560×1440 | 2K |
| 2160p | 3840×2160 | 4K Ultra HD |
| 4320p | 7680×4320 | 8K |

## 📝 תרומה

תרומות יתקבלו בברכה! אנא פתחו Issue או Pull Request.

## 📄 רישיון

הפרויקט מופץ ברישיון MIT. ראו קובץ LICENSE לפרטים נוספים.

---

<p align="center">
  נבנה עם ❤️ על ידי <strong>shoprdo63-lab</strong>
</p>
