import logging
from flask import Flask, session, redirect, render_template, request, url_for, jsonify
from models import Item, Category, Session


app = Flask(__name__)
session = Session()


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

    return render_template('index.html', categories=categories, items=items)


@app.route('/items/JSON')
def index_json():
    items = session.query(Item).all()    
    return jsonify(Items=[i.serialize for i in items])


@app.route('/item/<id>')
def show(id):
    item = session.query(Item).filter(Item.id==id).first()
    return render_template('item.html', action='Show', item=item)


@app.route('/item/add', methods=['GET', 'POST'])
def add():
    categories = session.query(Category).all()
    if request.method == 'POST':
        data = request.form.to_dict(flat=True)
        item = Item(**data)
        session.add(item)
        session.commit()
        return redirect(url_for('.index'))

    return render_template('item.html', action='Add', item={}, categories=categories)


@app.route('/category/add', methods=['GET', 'POST'])
def add_category():
    if request.method == 'POST':
        data = request.form.to_dict(flat=True)
        category = Category(**data)
        session.add(category)
        session.commit()
        return redirect(url_for('.index'))

    return render_template('category.html', action='Add', category={})


@app.route('/item/<id>/edit', methods=['GET', 'POST'])
def edit(id):
    categories = session.query(Category).all()
    item = session.query(Item).filter(Item.id==id).first()
    if request.method == 'POST':
        data = request.form.to_dict(flat=True)
        item.name = data['name']
        item.category_id = data['category_id']
        item.description = data['description']
        session.add(item)
        session.commit()
        return redirect(url_for('.show', id=item.id))

    return render_template('item.html', action='Edd', item=item, categories=categories)


@app.route('/item/<id>/delete', methods=['GET', 'POST'])
def delete(id):
    if request.method == 'POST':
        session.query(Item).filter(Item.id==id).delete()
        return redirect(url_for('.index'))

    return render_template('item.html', action='Delete', id=id)


@app.errorhandler(500)
def server_error(e):
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)