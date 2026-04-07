from pymongo import MongoClient
import certifi
import os

MONGO_URI = "mongodb+srv://dds_user:MySecurePass123@cluster0.lcf2ezo.mongodb.net/dds_db?retryWrites=true&w=majority&tls=true"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
print(client.list_database_names())
