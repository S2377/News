from flask import Flask, request, render_template, url_for, redirect, session
from authlib.integrations.flask_client import OAuth
import requests
from bs4 import BeautifulSoup
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk import pos_tag
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import psycopg2

app = Flask(__name__)
oauth = OAuth(app)

# github
app.config['SECRET_KEY'] = "THIS SHOULD BE SECRET"
app.config['GITHUB_CLIENT_ID'] = "0e6e81087ea9dbfa865e"
app.config['GITHUB_CLIENT_SECRET'] = "411db06f43cfc318241d3d30d747a0bedab735f8"

github = oauth.register(
    name='github',
    client_id=app.config["GITHUB_CLIENT_ID"],
    client_secret=app.config["GITHUB_CLIENT_SECRET"],
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

# GitHub admin usernames for verification
github_admin_usernames = ["Swarnali-sitare", "atmabodha"]

# Connect to PostgreSQL database
conn = psycopg2.connect(
    dbname="swarnali_fgi7",
    user="swarnali_fgi7_user",
    password="Qm72tC2yK12pyRSlDyidpmuM3KbDJBE9",
    host=dpg-cnn0jhi1hbls739j11mg-a,
    port="5432"
)
cur = conn.cursor()

# Create table if not exists
cur.execute('''
    CREATE TABLE IF NOT EXISTS news_articles (
        id SERIAL PRIMARY KEY,
        url TEXT,
        article_text TEXT,
        num_sentences INTEGER,
        num_words INTEGER
    )
''')
conn.commit()

@app.route('/')
def index():
    return render_template('newindex.html')

@app.route('/get_article', methods=['POST'])
def get_article():
    url = request.form['url']
    article_text = scrape_article(url)[0]
    heading=scrape_article(url)[1]
    num_sentences = len(sent_tokenize(article_text))
    num_words = len(word_tokenize(article_text))
    pos_tags = pos_tag(word_tokenize(article_text),tagset='universal')
    
    # Count the number of times each POS tag is used
    pos_tag_counts = {}
    for _, tag in pos_tags:
        pos_tag_counts[tag] = pos_tag_counts.get(tag, 0) + 1
    
    sid = SentimentIntensityAnalyzer()
    sentiment = sid.polarity_scores(article_text)
    polar1 = sentiment["neg"]
    polar2 = sentiment["pos"]
    if polar2>polar1:
        polarity='POSITIVE'
    elif polar1==polar2:
        polarity='NEUTRAL'
    else:
        polarity='NEGATIVE'
    
    # Store data in PostgreSQL table
    cur.execute('''
        INSERT INTO news_articles (url, article_text, num_sentences, num_words)
        VALUES (%s, %s, %s, %s)
    ''', (url, article_text, num_sentences, num_words))
    conn.commit()
    
    return render_template('analysis.html', article_text=article_text, url=scrape_article(url)[1],
                           num_sentences=num_sentences, num_words=num_words, pos_tag_counts=pos_tag_counts, sentiment_polarity=polarity)

@app.route('/history')
def history():
    # Fetch history from PostgreSQL table
    cur.execute('SELECT * FROM news_articles')
    articles = cur.fetchall()
    return render_template('history.html', articles=articles)

@app.route('/view_analysis/<int:article_id>') 
def view_analysis(article_id):
    # Fetch analysis data for a specific article from PostgreSQL table
    cur.execute('SELECT * FROM news_articles WHERE id = %s', (article_id,))
    article = cur.fetchone()
    
    # Count the number of times each POS tag is used for the article
    pos_tags = pos_tag(word_tokenize(article[2]),tagset='universal')
    pos_tag_counts = {}
    for _, tag in pos_tags:
        pos_tag_counts[tag] = pos_tag_counts.get(tag, 0) + 1
    url=article[1]
    heading=scrape_article(url)[1]
    
    return render_template('analysis.html', url=heading, article_text=article[2], 
                           num_sentences=article[3], num_words=article[4], pos_tag_counts=pos_tag_counts)

def scrape_article(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    heading = soup.title.string
    article_text = ''
    for paragraph in soup.find_all('p'):
        article_text += paragraph.text + ' '
    # Clean article text (remove extra whitespaces, special characters, etc.)
    article_text = ' '.join(article_text.split())
    return [article_text,heading]

# github
@app.route('/login/github')
def github_login():
    github = oauth.create_client('github')
    redirect_uri = url_for('github_authorize', _external=True)
    return github.authorize_redirect(redirect_uri)

# Github authorize route
@app.route('/login/github/authorize')
def github_authorize():
    try:
        github = oauth.create_client('github')
        token = github.authorize_access_token()
        session['github_token'] = token
        resp = github.get('user').json()
        print(f"\n{resp}\n")
        logged_in_username = resp.get('login')
        if logged_in_username in github_admin_usernames:
            # Fetch history from PostgreSQL table
            cur.execute('SELECT * FROM news_articles')
            articles = cur.fetchall()
            return render_template("history.html", articles=articles)
        else:
            return redirect(url_for('index'))
    except:
        return redirect(url_for('index'))

    
# Logout route for GitHub
@app.route('/logout/github')
def github_logout():
    session.clear()
    # session.pop('github_token', None)()
    print("logged out")
    # return redirect(url_for('index'))
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True,host = '0.0.0.0')
