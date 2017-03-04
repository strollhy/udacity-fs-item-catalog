from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Item, Category


db = create_engine('postgresql:///itemcatalog')
Session = sessionmaker(bind=db)


def create_table():
    Base.metadata.create_all(db)