import os
import re
import shutil
import urllib.request
import urllib.error
import json
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|shorts/|v/)?(?P<id>[A-Za-z0-9\-_]+)"
)

COMMON_YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'referer': 'https://www.youtube.com/',
    'headers': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    },
    'socket_timeout': 30,
    'retries': 3,
    'fragment_retries': 3,
    'file_access_retries': 3,
    'extractor_args': {
        'youtube': {
            'player_client': ['web'],
            'player_skip': ['webpage', 'config', 'js'],
        }
    },
}


def validate_url(url):
    return YOUTUBE_REGEX.match(url)


def cleanup_old_downloads(folder=DOWNLOAD_FOLDER, max_age_hours=2):
    now = datetime.now()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            file_age = now - datetime.fromtimestamp(os.path.getmtime(filepath))
            if file_age.total_seconds() > max_age_hours * 3600:
                os.remove(filepath)


def get_video_info(url):
    ydl_opts = {**COMMON_YDL_OPTS, 'listformats': False}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        # 1. Video+Audio merged formats (pre-merged by YouTube)
        merged_video_formats = []
        for f in info.get('formats', []):
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                merged_video_formats.append(f)
        
        # 2. Video-only streams (will be merged with audio)
        video_only_map = {}
        for f in info.get('formats', []):
            if f.get('vcodec') == 'none' or f.get('acodec') != 'none':
                continue
            q = f.get('quality_label') or f.get('format_note', 'unknown')
            res = f.get('width', 0) or 0
            if q not in video_only_map or res > video_only_map[q].get('width', 0):
                video_only_map[q] = f
        
        # 3. Audio-only formats
        audio_formats = []
        best_audio = None
        for f in info.get('formats', []):
            if f.get('vcodec') != 'none' or f.get('acodec') == 'none':
                continue
            # Track best audio for merging
            abr = f.get('abr', 0) or 0
            if best_audio is None or abr > (best_audio.get('abr', 0) or 0):
                best_audio = f
            audio_formats.append(f)
        
        # Build response categories
        video_formats = []
        
        # Add merged formats first (ready to use)
        seen_qualities = set()
        for f in sorted(merged_video_formats, key=lambda x: x.get('height', 0) or 0, reverse=True):
            q = f.get('quality_label') or f.get('format_note', 'unknown')
            if q not in seen_qualities:
                seen_qualities.add(q)
                video_formats.append({
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'quality': q,
                    'resolution': f.get('resolution', 'unknown'),
                    'filesize': f.get('filesize') or f.get('filesize_approx'),
                    'type': 'video',
                    'has_audio': True,
                })
        
        # Add video-only streams (higher qualities that need audio merge)
        for q, f in sorted(video_only_map.items(), key=lambda x: x[1].get('width', 0), reverse=True):
            if q not in seen_qualities:
                seen_qualities.add(q)
                video_formats.append({
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'quality': q,
                    'resolution': f.get('resolution', 'unknown'),
                    'filesize': f.get('filesize') or f.get('filesize_approx'),
                    'type': 'video',
                    'has_audio': False,
                    'audio_format_id': best_audio['format_id'] if best_audio else None,
                })
        
        # Audio formats
        audio_list = []
        seen_audio = set()
        for f in sorted(audio_formats, key=lambda x: x.get('abr', 0) or 0, reverse=True):
            abr = f.get('abr', 0)
            key = f"{f.get('ext', 'm4a')}_{abr}"
            if key not in seen_audio:
                seen_audio.add(key)
                audio_list.append({
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'quality': f"{int(abr)}kbps" if abr else 'audio',
                    'resolution': 'audio only',
                    'filesize': f.get('filesize') or f.get('filesize_approx'),
                    'type': 'audio',
                    'has_audio': True,
                })
        
        return {
            'title': info.get('title', 'video'),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail', ''),
            'uploader': info.get('uploader', ''),
            'video_formats': video_formats,
            'audio_formats': audio_list,
        }


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/blog', methods=['GET'])
def blog():
    return render_template('blog.html')


ARTICLES = {
    '4k-guide': {
        'title': 'איך להוריד סרטוני YouTube באיכות 4K?',
        'desc': 'מדריך שלב-אחר-שלב להורדת סרטונים באיכות 4K Ultra HD מ-YouTube',
        'tag': 'מדריך מקיף',
        'read_time': '8 דקות קריאה',
        'gradient': 'linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%)',
        'icon': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>',
        'content': '''
        <h2>מהי איכות 4K?</h2>
        <p>4K Ultra HD היא רזולוציה של 3840×2160 פיקסלים - פי 4 מאיכות Full HD רגילה. YouTube תומך בהעלאת סרטונים באיכות זו מאז 2010, והיום כמעט כל תוכן חדש זמין ב-4K.</p>

        <h2>איך לבחור את האיכות הנכונה?</h2>
        <p>כשמורידים סרטון, חשוב לשים לב למספר דברים:</p>
        <ul>
            <li><strong>בדקו זמינות:</strong> לא כל הסרטונים ב-YouTube זמינים ב-4K. היוצר צריך להעלות את הקובץ באיכות זו.</li>
            <li><strong>בחרו פורמט:</strong> MP4 הוא הכי תואם למכשירים. WEBM נותן איכות דומה אבל פחות נתמך.</li>
            <li><strong>שימו לב לגודל:</strong> סרטון 4K דקה אחת שוקל בערך 400MB. ודאו שיש לכם מספיק מקום.</li>
        </ul>

        <h2>הפורמטים הטובים ביותר</h2>
        <p>YouTube מציע מספר אפשרויות להורדה:</p>
        <ul>
            <li><strong>2160p (4K):</strong> 3840×2160 - האיכות הגבוהה ביותר</li>
            <li><strong>1440p (2K):</strong> 2560×1440 - איכות מעולה, קובץ קטן יותר</li>
            <li><strong>1080p (FHD):</strong> 1920×1080 - מספיק למסכים רגילים</li>
        </ul>

        <h2>טיפים חשובים</h2>
        <p>כדי לשמור על איכות מקסימלית:</p>
        <ul>
            <li>השתמשו בכלי הורדה אמין שתומך ב-4K</li>
            <li>ודאו שיש לכם חיבור אינטרנט מהיר (50Mbps+ להורדת 4K)</li>
            <li>בדקו את הגדרות התצוגה במכשיר שלכם</li>
            <li>שמרו את הקבצים בכונן מהיר (SSD מומלץ)</li>
        </ul>

        <h2>סיכום</h2>
        <p>הורדת סרטונים ב-4K היא פשוטה כשיש את הכלים הנכונים. פשוט הדביקו את הקישור, בחרו את האיכות הרצויה, והתחילו להוריד!</p>
        '''
    },
    'tips': {
        'title': '5 סיבות להשתמש במוריד סרטונים מקצועי',
        'desc': 'לא כל כלי הורדה נוצרו שווים - למדו למה לבחור בכלי מקצועי',
        'tag': 'טיפים מקצועיים',
        'read_time': '5 דקות קריאה',
        'gradient': 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
        'icon': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>',
        'content': '''
        <h2>1. איכות מקסימלית</h2>
        <p>מוריד מקצועי שומר על האיכות המקורית של הסרטון ללא דחיסה מיותרת. כלי חינמיים רבים מפחיתים את האיכות או מוסיפים סימני מים.</p>

        <h2>2. מהירות הורדה</h2>
        <p>שרתים מקצועיים מציעים חיבורים מהירים יותר, מה שמאפשר הורדת סרטונים ארוכים בזמן סביר. כלים פשוטים לעיתים מוגבלים במהירות.</p>

        <h2>3. תמיכה בכל הפורמטים</h2>
        <p>מוריד מקצועי תומך בכל איכויות הוידאו והאודיו: 4K, 1080p, 720p, MP3, AAC ועוד. אין צורך להשתמש בכלי נפרד לכל פורמט.</p>

        <h2>4. בטיחות</h2>
        <p>אתרים מקצועיים מאובטחים ולא מכילים פרסומות זדוניות או וירוסים. הם גם לא שומרים היסטוריית הורדות או מידע אישי.</p>

        <h2>5. נוחות שימוש</h2>
        <p>ממשק נקי ופשוט חוסך זמן. אין צורך להתקין תוכנות, ליצור חשבונות, או להתמודד עם מגבלות.</p>
        '''
    },
    'mp4-vs-webm': {
        'title': 'MP4 לעומת WEBM - איזה פורמט עדיף?',
        'desc': 'הבנה מעמיקה של פורמטי הוידאו ב-YouTube',
        'tag': 'הסבר טכני',
        'read_time': '6 דקות קריאה',
        'gradient': 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
        'icon': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        'content': '''
        <h2>מה זה MP4?</h2>
        <p>MP4 (MPEG-4 Part 14) הוא פורמט הקובץ הכי פופולרי בעולם. הוא נתמך על ידי כמעט כל מכשיר: טלפונים, טלוויזיות, מחשבים, וקונסולות משחקים.</p>

        <h2>מה זה WEBM?</h2>
        <p>WEBM הוא פורמט קוד פתוח שפותח על ידי Google. הוא מיועד בעיקר לשימוש באינטרנט ותומך בסטרימינג ישיר.</p>

        <h2>השוואה טכנית</h2>
        <table>
            <tr><th>תכונה</th><th>MP4</th><th>WEBM</th></tr>
            <tr><td>תמיכה במכשירים</td><td>99%</td><td>80%</td></tr>
            <tr><td>גודל קובץ</td><td>בינוני</td><td>קטן יותר</td></tr>
            <tr><td>איכות</td><td>מעולה</td><td>מעולה</td></tr>
            <tr><td>סטרימינג</td><td>כן</td><td>כן (טוב יותר)</td></tr>
        </table>

        <h2>מה לבחור?</h2>
        <p><strong>MP4</strong> - אם אתם רוצים תאימות מקסימלית עם כל המכשירים.</p>
        <p><strong>WEBM</strong> - אם גודל הקובץ חשוב ואתם משחקים בעיקר במחשב.</p>
        '''
    },
    'safety': {
        'title': 'איך להוריד סרטונים בצורה בטוחה?',
        'desc': 'מדריך בטיחות מקיף להורדת תוכן מ-YouTube',
        'tag': 'בטיחות',
        'read_time': '4 דקות קריאה',
        'gradient': 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        'icon': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>',
        'content': '''
        <h2>סכנות בהורדת סרטונים</h2>
        <p>רבים לא יודעים, אבל הורדת סרטונים ממקורות לא אמינים יכולה להיות מסוכנת:</p>
        <ul>
            <li>אתרים עם פרסומות זדוניות</li>
            <li>התקנת תוכנות לא רצויות</li>
            <li>גניבת מידע אישי</li>
            <li>וירוסים ותוכנות ריגול</li>
        </ul>

        <h2>איך להימנע מסכנות?</h2>
        <p>הנה כללי זהב לבטיחות:</p>
        <ul>
            <li>השתמשו רק באתרים אמינים וידועים</li>
            <li>אין להתקין תוכנות כדי להוריד סרטון</li>
            <li>בדקו שהאתר משתמש ב-HTTPS</li>
            <li>קראו ביקורות על האתר לפני השימוש</li>
            <li>השתמשו בתוכנת אנטי-וירוס מעודכנת</li>
        </ul>

        <h2>איך לזהות אתר זדוני?</h2>
        <p>סימני אזהרה:</p>
        <ul>
            <li>בקשה להתקין תוספים או תוכנות</li>
            <li>חלונות קופצים רבים</li>
            <li>כתובת לא ברורה או חשודה</li>
            <li>איות לקוי באנגלית</li>
            <li>בקשה לפרטי אשראי</li>
        </ul>
        '''
    },
    'legal': {
        'title': 'מה החוק אומר על הורדת סרטוני YouTube?',
        'desc': 'סקירה משפטית מקיפה של זכויות יוצרים ב-YouTube',
        'tag': 'חוקיות',
        'read_time': '7 דקות קריאה',
        'gradient': 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
        'icon': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"/></svg>',
        'content': '''
        <h2>זכויות יוצרים ב-YouTube</h2>
        <p>מדיניות YouTube ברורה: הורדת תוכן ללא אישור עשויה להפר זכויות יוצרים. אך יש מצבים שבהם הורדה מותרת:</p>

        <h2>שימוש הוגן (Fair Use)</h2>
        <p>במקרים מסוימים, שימוש בתוכן מוגן בזכויות יוצרים עשוי להיות חוקי:</p>
        <ul>
            <li>שימוש חינוכי או אקדמי</li>
            <li>ביקורת או פרודיה</li>
            <li>חדשות ודיווח</li>
            <li>מחקר ומדע</li>
        </ul>

        <h2>Creative Commons</h2>
        <p>יוצרים רבים מציעים רישיון Creative Commons שמאפשר:</p>
        <ul>
            <li>שיתוף תוכן עם ייחוס</li>
            <li>שימוש לא מסחרי</li>
            <li>יצירות נגזרות</li>
        </ul>

        <h2>מה מותר לעשות?</h2>
        <p>באופן כללי:</p>
        <ul>
            <li>שמירת סרטונים לצפייה אופליין לשימוש אישי</li>
            <li>שימוש בתוכן ברישיון פתוח</li>
            <li>שימוש לצרכים חינוכיים</li>
        </ul>

        <h2>מה אסור?</h2>
        <ul>
            <li>שיתוף מחדש ללא אישור</li>
            <li>שימוש מסחרי בתוכן מוגן</li>
            <li>מכירת תוכן שהורד</li>
        </ul>
        '''
    },
    'technology': {
        'title': 'איך עובדת טכנולוגיית ההורדה מ-YouTube?',
        'desc': 'מבט פנימה לארכיטקטורה של מורידי YouTube',
        'tag': 'טכנולוגיה',
        'read_time': '10 דקות קריאה',
        'gradient': 'linear-gradient(135deg, #ec4899 0%, #f43f5e 100%)',
        'icon': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>',
        'content': '''
        <h2>הארכיטקטורה של YouTube</h2>
        <p>YouTube מאחסן סרטונים בצורה מורכבת. כל סרטון מפורק למקטעים קטנים ומקודד במספר איכויות ופורמטים שונים.</p>

        <h2>איך yt-dlp עובד?</h2>
        <p>yt-dlp הוא הכלי המקצועי ביותר להורדת תוכן מ-YouTube. הוא עובד בשלושה שלבים:</p>
        <ol>
            <li><strong>חילוץ מידע:</strong> מנתח את דף ה-YouTube ומוצא את כל הפורמטים הזמינים</li>
            <li><strong>בחירת פורמט:</strong> מאפשר לבחור בין וידאו, אודיו, או שניהם</li>
            <li><strong>הורדה ומיזוג:</strong> מוריד את הזרמים וממזג אותם לקובץ אחד</li>
        </ol>

        <h2>פורמטי DASH</h2>
        <p>YouTube משתמש בטכנולוגיית DASH (Dynamic Adaptive Streaming):</p>
        <ul>
            <li>וידאו ואודיו מופרדים לשני קבצים נפרדים</li>
            <li>הדפדפן בוחר את האיכות המתאימה בזמן אמת</li>
            <li>מוריד צריך למזג את השניים לאחר ההורדה</li>
        </ul>

        <h2>אלגוריתמים של דחיסה</h2>
        <p>YouTube משתמש במספר קודקים:</p>
        <ul>
            <li><strong>H.264/AVC:</strong> הקודק הנפוץ ביותר, תואם לכל מכשיר</li>
            <li><strong>VP9:</strong> קודק חינמי של Google, יעיל יותר</li>
            <li><strong>AV1:</strong> הדור הבא, איכות טובה יותר בגודל קטן</li>
        </ul>
        '''
    }
}


@app.route('/blog/<slug>')
def article(slug):
    article = ARTICLES.get(slug)
    if not article:
        return render_template('blog.html'), 404
    return render_template('article.html', **article)


INVIDIOUS_INSTANCES = [
    'https://vid.puffyan.us',
    'https://inv.riverside.rocks',
    'https://iv.datura.network',
    'https://yt.artemislena.eu',
    'https://invidious.fdn.fr',
    'https://y.com.sb',
    'https://invidious.privacydev.net',
    'https://iv.nboeck.de',
    'https://iv.melmac.space',
    'https://invidious.slipfox.xyz',
]


def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})',
        r'youtube\.com/embed/([A-Za-z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_from_invidious(video_id):
    """Fetch video info from Invidious API (server-side, no CORS issues)"""
    import urllib.error
    errors = []
    for base in INVIDIOUS_INSTANCES:
        try:
            req = urllib.request.Request(
                f'{base}/api/v1/videos/{video_id}',
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                }
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_msg = f'{base}: HTTP {e.code}'
            errors.append(error_msg)
            print(error_msg)
            continue
        except Exception as e:
            error_msg = f'{base}: {str(e)}'
            errors.append(error_msg)
            print(error_msg)
            continue
    raise Exception(f'All Invidious instances failed: {"; ".join(errors)}')


@app.route('/api/proxy/info', methods=['POST'])
def proxy_video_info():
    """Proxy video info through Invidious (server-side, no CORS)"""
    data = request.get_json()
    url = data.get('url', '').strip()

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    try:
        invidious_data = fetch_from_invidious(video_id)

        # Parse formats similar to client-side
        video_formats = []
        seen_qualities = set()

        for fmt in invidious_data.get('adaptiveFormats', []):
            if fmt.get('type', '').startswith('video/'):
                quality = fmt.get('qualityLabel') or fmt.get('resolution') or 'unknown'
                if quality in seen_qualities:
                    continue
                seen_qualities.add(quality)
                video_formats.append({
                    'format_id': fmt.get('itag') or fmt.get('url'),
                    'quality': quality,
                    'resolution': fmt.get('resolution') or quality,
                    'url': fmt.get('url'),
                    'has_audio': False,
                    'ext': fmt.get('container') or 'mp4',
                })

        audio_formats = []
        seen_audio = set()

        for fmt in invidious_data.get('adaptiveFormats', []):
            if fmt.get('type', '').startswith('audio/'):
                abr = fmt.get('bitrate', 0)
                if abr:
                    abr = round(abr / 1000)
                key = f"{fmt.get('container', 'm4a')}_{abr}"
                if key in seen_audio:
                    continue
                seen_audio.add(key)
                audio_formats.append({
                    'format_id': fmt.get('itag') or fmt.get('url'),
                    'quality': f"{abr}kbps" if abr else 'אודיו',
                    'resolution': 'audio only',
                    'url': fmt.get('url'),
                    'has_audio': True,
                    'ext': fmt.get('container') or 'm4a',
                })

        # Combined formats
        for fmt in invidious_data.get('formatStreams', []):
            if fmt.get('type', '').startswith('video/'):
                quality = fmt.get('qualityLabel') or fmt.get('resolution') or 'unknown'
                if quality not in seen_qualities:
                    seen_qualities.add(quality)
                    video_formats.append({
                        'format_id': fmt.get('itag') or fmt.get('url'),
                        'quality': quality,
                        'resolution': fmt.get('resolution') or quality,
                        'url': fmt.get('url'),
                        'has_audio': True,
                        'ext': fmt.get('container') or 'mp4',
                    })

        return jsonify({
            'title': invidious_data.get('title', 'video'),
            'duration': invidious_data.get('lengthSeconds'),
            'thumbnail': invidious_data.get('videoThumbnails', [{}])[0].get('url', ''),
            'uploader': invidious_data.get('author', ''),
            'video_formats': video_formats,
            'audio_formats': audio_formats,
        })
    except Exception as e:
        return jsonify({'error': f'Failed to fetch: {str(e)}'}), 500


@app.route('/api/info', methods=['POST'])
def video_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url or not validate_url(url):
        return jsonify({'error': 'Invalid or missing YouTube URL'}), 400
    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')
    download_type = data.get('type', 'video')

    if not url or not validate_url(url):
        return jsonify({'error': 'Invalid or missing YouTube URL'}), 400

    cleanup_old_downloads()

    try:
        info_opts = {**COMMON_YDL_OPTS}
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get('title', 'video')
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:50]
        if not safe_title:
            safe_title = 'video'

        if download_type == 'audio':
            output_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}_{format_id}.mp3")
            ydl_opts = {
                **COMMON_YDL_OPTS,
                'format': format_id if format_id != 'best' else 'bestaudio',
                'outtmpl': output_path,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            }
            download_name = f"{safe_title}.mp3"
        else:
            output_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}_{format_id}.mp4")
            fmt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            if format_id and format_id != 'best':
                fmt = f"{format_id}+bestaudio[ext=m4a]/{format_id}/best"
            ydl_opts = {
                **COMMON_YDL_OPTS,
                'format': fmt,
                'outtmpl': output_path,
                'merge_output_format': 'mp4',
            }
            download_name = f"{safe_title}.mp4"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(output_path):
            return send_file(output_path, as_attachment=True, download_name=download_name)
        return jsonify({'error': 'Download failed, file not found'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/robots.txt')
def robots():
    return """User-agent: *
Allow: /
Disallow: /downloads/
Sitemap: https://youtube-downolder.onrender.com/sitemap.xml
""", 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/sitemap.xml')
def sitemap():
    base_url = 'https://youtube-downolder.onrender.com'
    today = datetime.now().strftime('%Y-%m-%d')

    urls = [
        {'loc': f'{base_url}/', 'priority': '1.0', 'changefreq': 'weekly'},
        {'loc': f'{base_url}/blog', 'priority': '0.9', 'changefreq': 'weekly'},
    ]

    for slug in ARTICLES.keys():
        urls.append({
            'loc': f'{base_url}/blog/{slug}',
            'priority': '0.8',
            'changefreq': 'monthly'
        })

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for u in urls:
        xml.append('  <url>')
        xml.append(f'    <loc>{u["loc"]}</loc>')
        xml.append(f'    <lastmod>{today}</lastmod>')
        xml.append(f'    <changefreq>{u["changefreq"]}</changefreq>')
        xml.append(f'    <priority>{u["priority"]}</priority>')
        xml.append('  </url>')

    xml.append('</urlset>')

    return '\n'.join(xml), 200, {'Content-Type': 'application/xml; charset=utf-8'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
