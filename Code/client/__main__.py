from .client import Client

client = Client()

client.list_files()
client.download_file("duck.jpg")

client.close()