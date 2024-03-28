
############################################## import required packages and modules  ##################################

from flask import Flask, render_template, redirect, url_for, session, request, flash
from bs4 import BeautifulSoup
import nltk
import requests
import json
from nltk import pos_tag, word_tokenize
from nltk.corpus import stopwords
import psycopg2
import urllib.request
from jinja2 import Template
from collections import defaultdict
from authlib.integrations.flask_client import OAuth
from werkzeug import *
app = Flask(__name__)

# Initialize NLTK
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')

###########################################       Database setup   ###########################################################

database_url = "dpg-cnn1aoqcn0vc738gmuvg-a.oregon-postgres.render.com"
host = f"{database_url}"
conn = psycopg2.connect(  
    host = host,
    dbname="article_analyaser",
    user="article_analyaser_user",
    password="sqGshL8qhJfDTfu3dAs1UwMXI1YueDq9"
)


cur = conn.cursor()
  # for storing user credentials
cur.execute("""                     
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
""")
conn.commit()


# for storing scraped news articles and their analysis
cur.execute("""
    CREATE TABLE IF NOT EXISTS news_articles (
        id SERIAL PRIMARY KEY,
        URL TEXT,
        Title varchar,
        Text TEXT,
        Num_words int,
        Num_sentences int,
        Pos_tag TEXT
      
    )
""")
conn.commit()


######################################### helper function for Cleaning  ############################################

def get_html_content(url):
    # Fetch HTML content from the given URL
    response = requests.get(url)
    return response.text

def extract_title(html_content):
    # Extract and return the title of the webpage
    soup = BeautifulSoup(html_content, 'html.parser')
    title = soup.title.string.strip()
    return title

def extract_body(content):
    # Extract and return the body content of the webpage from specific HTML elements
    soup = BeautifulSoup(content, 'html.parser')
    # Find the main content <div> element (adjust class name as needed)
    main_content_div = soup.find('div', class_='full-details')
    if main_content_div:
        # Find all <p> elements within the main content <div>
        news_paragraphs = main_content_div.find_all('p')
        # Concatenate text from all <p> elements
        body_text = '\n'.join(paragraph.get_text(strip=True) for paragraph in news_paragraphs)
        return body_text
    else:
        return "Main content <div> not found"

def extract_links(html_content):
    # Extract and return links from the webpage
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    for link in soup.find_all('a', href=True):
        links.append(link['href'])
    return links
    
###################################################### routing  ###########################################################

# @app.route('/')
# def index():
#     return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    url = request.form['url']
    
    content = get_html_content(url)
    title = extract_title(content)
    news_text = extract_body(content)
    # Analyze the text
    sentences = nltk.sent_tokenize(news_text)
    words = nltk.word_tokenize(news_text)
    num_sentences = len(sentences)
    num_words = len(words)
    upos_tag_list = nltk.pos_tag(words, tagset='universal')
    
    upos_dict = {}
    for i in upos_tag_list:
        if i[1] not in upos_dict.keys() :
            upos_dict[i[1]] = 1
        else:
            upos_dict[i[1]] += 1
            
    # print(upos_dict)
    
    noun_pronoun_ratio = int(upos_dict['NOUN']/upos_dict['PRON'])
    verb_adv_ratio = int(upos_dict['VERB']/upos_dict['ADV'])
    
    links = extract_links(content)
    # print(links)
    count_hyperlink = 0
    for link in links:
        count_hyperlink +=1

    
    # Store the data in the database
    cur.execute("""
        INSERT INTO news_articles (URL, Title, Text, Num_words, Num_sentences, Pos_tag)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (url, title, news_text, num_words, num_sentences, str(upos_dict)))
    conn.commit()

    
    return render_template('analysis.html', url=url, title = title ,news_text = news_text,num_sentences = num_sentences, num_words = num_words,count_hyperlink = count_hyperlink, upos_dict= upos_dict,
                           noun_pronoun_ratio = noun_pronoun_ratio,verb_adv_ratio = verb_adv_ratio)


def fetch_history():
    cur.execute("SELECT * FROM news_articles")
    data = cur.fetchall()
    return data 


    
########################################    Authentication  ###################################################

oauth = OAuth(app)
app.config['SECRET_KEY'] = "secret"
app.config['GITHUB_CLIENT_ID'] = "Iv1.548ac24ff7f506c6"
app.config['GITHUB_CLIENT_SECRET'] = "1bd71f728e3b19c8c7fd4243924483089f438c08"

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
github_admin_usernames = ["rashu-2375", "atmabodh",'S2377']

@app.route('/login/github') # this route redirects the user to the GitHub authorization page
def github_login():
    github = oauth.create_client('github')
    redirect_uri = url_for('github_authorize', _external=True)
    return github.authorize_redirect(redirect_uri)

# Github authorize route that handles the authorization callback from GitHub 
# and retrieves the user's access token and data.
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
            data = fetch_history()
            cur.execute("SELECT username FROM users")
            usernames = [row[0] for row in cur.fetchall()]
            return render_template("admin.html", articles = data,usernames = usernames)
        
        else:
            return redirect(url_for('index'))
    except:
        return redirect(url_for('index'))

    
# Logout route for GitHub
@app.route('/logout/github')
def github_logout():
    session.clear()
    # session.pop('github_token', None)()
    print("logout")
    # return redirect(url_for('index'))
    return redirect(url_for('index'))


######################################### Login and Signup #############################################

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the username already exists
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()
        if existing_user:
            flash('Username already taken')
        else:
            # Insert the new user into the database
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
            flash('Account created successfully! Please log in.')
            return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the username and password are correct
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()

        if user:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@app.route("/") 
def home():
    if 'logged_in' in session:
        return render_template("index.html", username = session['username'])
    else:
        return redirect(url_for('signup'))

    # return redirect("signup.html")
    
    
@app.route('/home')
def back_home():
    return redirect(url_for('home'))
    # return redirect(url_for('submit'))



@app.route("/logout", methods=['GET', 'POST'])
def logout():
    # Clear the session
    session.pop('logged_in', None)
    session.pop('username', None)
    # Redirect to the login page
    return redirect(url_for('login'))

    
if __name__ == '__main__':
    app.run(debug=True, host = '0.0.0.0')
