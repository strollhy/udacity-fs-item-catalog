import logging
from flask import Flask, redirect, render_template, request, url_for, jsonify, flash
from models import Item, Category, User, Session

# For auth
from flask import session as login_session
import random, string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']

app = Flask(__name__)
session = Session()


def __render_template(template, **kwargs):
    return render_template(template,
        username=login_session.get('username'),
        user_id=login_session.get('user_id'),
        **kwargs)


# User Auth
@app.route('/login')
def login():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return __render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter', 401))
        return response
    code = request.data
    try:
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps('Token\'s user ID doesn\'t match given user ID.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    # create user
    user = session.query(User).filter(User.email==str(data['email'])).first()
    if not user:
        user = User()
        user.name = data['name']
        user.picture = str(data['picture'])
        user.email = str(data['email'])
        session.add(user)
        session.commit()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    login_session['user_id'] = user.id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    print "done!"
    return output


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session['access_token']
    if access_token is None:
        print 'Access Token is None'
        return redirect(url_for('.index'))

    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result

    del login_session['access_token']
    del login_session['gplus_id']
    del login_session['username']
    del login_session['email']
    del login_session['picture']

    return redirect(url_for('.index'))

# Item endpoints
@app.route('/')
@app.route('/items')
def index():
    category_name = request.args.get('category')
    categories = session.query(Category).all()

    if category_name:
        category = session.query(Category).filter(Category.name==category_name).first()
        items = session.query(Item).filter(Item.category_id==category.id).all()
    else:
        items = session.query(Item).all()

    return __render_template('index.html', categories=categories, items=items)


@app.route('/items/JSON')
def index_json():
    items = session.query(Item).all()    
    return jsonify(Items=[i.serialize for i in items])


@app.route('/item/<id>')
def show(id):
    item = session.query(Item).filter(Item.id==id).first()
    return __render_template('item.html', action='Show', item=item)


@app.route('/item/add', methods=['GET', 'POST'])
def add():
    if 'username' not in login_session:
        return redirect(url_for('.login'))

    categories = session.query(Category).all()
    if request.method == 'POST':
        data = request.form.to_dict(flat=True)
        item = Item(**data)
        item.user_id = login_session.get('user_id')
        session.add(item)
        session.commit()
        return redirect(url_for('.index'))

    return __render_template('item.html', action='Add', item={}, categories=categories)


@app.route('/item/<id>/edit', methods=['GET', 'POST'])
def edit(id):
    if 'username' not in login_session:
        return redirect(url_for('.login'))

    categories = session.query(Category).all()
    item = session.query(Item).filter(Item.id==id).first()
    if item.user_id != login_session.get('user_id'):
        flash('You are not allowed to edit this item.', 'Unauthorized')
        return redirect(url_for('.show', id=item.id))

    if request.method == 'POST':
        data = request.form.to_dict(flat=True)
        item.name = data['name']
        item.category_id = data['category_id']
        item.description = data['description']
        session.add(item)
        session.commit()
        return redirect(url_for('.show', id=item.id))

    return __render_template('item.html', action='Edd', item=item, categories=categories)


@app.route('/item/<id>/delete', methods=['GET', 'POST'])
def delete(id):
    if 'username' not in login_session:
        return redirect(url_for('.login'))

    item = session.query(Item).filter(Item.id==id).first()
    if item.user_id != login_session.get('user_id'):
        flash('You are not allowed to delete this item.', 'Unauthorized')
        return redirect(url_for('.show', id=item.id))

    if request.method == 'POST':
        session.query(Item).filter(Item.id==id).delete()
        return redirect(url_for('.index'))

    return __render_template('item.html', action='Delete', id=id)


@app.route('/category/add', methods=['GET', 'POST'])
def add_category():
    if 'username' not in login_session:
        return redirect(url_for('.login'))

    if request.method == 'POST':
        data = request.form.to_dict(flat=True)
        category = Category(**data)
        category.user_id = login_session.get('user_id')
        session.add(category)
        session.commit()
        return redirect(url_for('.index'))

    return __render_template('category.html', action='Add', category={})


@app.errorhandler(500)
def server_error(e):
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500
 
if __name__ == '__main__':
    app.secret_key = 'A0Zr98j/3yX R~STRO!jmN]LWX/,?RT'
    app.run(host='0.0.0.0', port=8080, debug=True)