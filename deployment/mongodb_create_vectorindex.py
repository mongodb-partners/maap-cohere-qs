import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.operations import SearchIndexModel
from dotenv import load_dotenv
import os
import time
import json

# Load environment variables
load_dotenv()

# Constants
MONGODB_URI = "mongodb+srv://cohere:pass123@demo.fmxyq.mongodb.net/" #os.getenv("MONGO_URI")
POLL_INTERVAL = 5  # seconds


# Helper function to create and wait for a search index
def create_and_wait_for_search_index(collection, index_model):
    try:
        # Check if the collection exists before creating the index
        if collection.name not in collection.database.list_collection_names():
            print(f"Collection '{collection.name}' does not exist. Creating it now.")
            collection.database.create_collection(
                collection.name
            )  # Create the collection

        result = collection.create_search_index(model=index_model)
        print(f"New search index named {result} is building.")
        print("Polling to check if the index is ready. This may take up to a minute.")

        while True:
            indices = list(collection.list_search_indexes(result))
            if indices and indices[0].get("queryable"):
                break
            time.sleep(POLL_INTERVAL)

        print(f"{result} is ready for querying.")
        return result
    except pymongo.errors.PyMongoError as e:
        print(f"Error creating search index: {e}")
        return None  # Return None to indicate failure


# Initialize MongoDB client
print("MongoDB URI -- ", MONGODB_URI)
client = MongoClient(MONGODB_URI)
db = client["asset_management_use_case"]
collection = db["market_reports"]

# Load data from file
try:
    with open("data.json", "r") as file:
        data = json.load(file)
except FileNotFoundError:
    print("Error: The file data.json was not found.")
    data = []
except json.JSONDecodeError:
    print("Error: Failed to decode JSON from the file.")
    data = []

if data:
    # Remove _id field from data (if exists)
    for doc in data:
        if "_id" in doc:
            del doc["_id"]

    # Bulk insert
    try:
        collection.delete_many({})
        result = collection.insert_many(data)
        print(f"Inserted {len(result.inserted_ids)} documents.")
    except pymongo.errors.BulkWriteError as e:
        print(f"Bulk write error occurred: {e.details}")
    except pymongo.errors.PyMongoError as e:
        print(f"Error inserting data: {e}")
else:
    print("No data to insert. Exiting.")

# Define search index models
index_models = [
    {
        "database": "asset_management_use_case",
        "collection": "market_reports",
        "index_model": SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": 1024,
                        "similarity": "cosine"
                    },
                    {
                        "type": "filter",
                        "path": "key_metrics.p_e_ratio"
                    },
                    {
                        "type": "filter",
                        "path": "key_metrics.market_cap"
                    },
                    {
                        "type": "filter",
                        "path": "key_metrics.dividend_yield"
                    },
                    {
                        "type": "filter",
                        "path": "key_metrics.current_stock_price"
                    }
                ]
            },
            name="vector_index",
            type="vectorSearch",
        ),
    }
]

# Process each database and collection
for model in index_models:
    db = client[model["database"]]
    coll = db[model["collection"]]
    index_result = create_and_wait_for_search_index(coll, model["index_model"])
    if index_result is None:
        print(f"Skipping index creation for {model['database']}.{model['collection']}")
    else:
        print(f"Search index created for {model['database']}.{model['collection']}.")

# Close the MongoDB client
client.close()