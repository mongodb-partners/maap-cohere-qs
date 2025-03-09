from typing import Dict, Optional, List
import pymongo
import os
import cohere
from dotenv import load_dotenv
from pathlib import Path

# Specify the path to your .env file
env_path = Path('scripts/.env')

DATABASE = "asset_management_use_case"
COLLECTION = "market_reports"

class CohereChat:
    def __init__(self, system: str = "", 
                 database: str = DATABASE,
                 collection: str = COLLECTION, 
                 history_params: Optional[Dict[str, str]] = None):
        
        # Load environment variables from a .env file
        load_dotenv(dotenv_path=env_path)

        # Ensure the required environment variables are set
        required_env_vars = ["COHERE_API_KEY", "MONGO_URI"]
        for var in required_env_vars:
          if var not in os.environ:
            raise EnvironmentError(f"Missing required environment variable: {var}")

        self.co = cohere.Client(os.environ.get("COHERE_API_KEY"))
        MONGO_URI = os.environ["MONGO_URI"]
        self.system = system
        self.history_params = history_params or {}

        # Use the connection string from history_params
        self.client = pymongo.MongoClient(self.history_params.get('connection_string', MONGO_URI))

        # Use the database parameter
        self.db = self.client[database]

        # Use the collection parameter
        self.collection = self.db[collection]

        # Use the history_collection from history_params, or default to "chat_history"
        self.history_collection = self.db[self.history_params.get('history_collection', 'chat_history')]

        # Use the session_id from history_params, or default to "default_session"
        self.session_id = self.history_params.get('session_id', 'default_session')

    def add_to_history(self, message: str, prefix: str = ""):
      self.history_collection.insert_one({
        'session_id': self.session_id,
        'message': message,
        'prefix': prefix
      })

    def get_chat_history(self) -> List[Dict[str, str]]:
      history = self.history_collection.find({'session_id': self.session_id}).sort('_id', 1)
      return [{"role": "user" if item['prefix'] == "USER" else "chatbot", "message": item['message']} for item in history]

    def rerank_documents(self, query: str, documents: List[Dict], top_n: int = 3) -> List[Dict]:
      rerank_docs = [
          {
            'company': doc['company'],
            'combined_attributes': doc['combined_attributes']
          }
          for doc in documents
          if doc['combined_attributes'].strip()
      ]

      if not rerank_docs:
          print("No valid documents to rerank.")
          return []

      try:
          response = self.co.rerank(
              query=query,
              documents=rerank_docs,
              top_n=top_n,
              model="rerank-english-v3.0",
              rank_fields=["company", "combined_attributes"]
          )

          top_documents_after_rerank = [
              {
                  'company': rerank_docs[result.index]['company'],
                  'combined_attributes': rerank_docs[result.index]['combined_attributes'],
                  'relevance_score': result.relevance_score
              }
              for result in response.results
          ]

          print(f"\nHere are the top {top_n} documents after rerank:")
          for doc in top_documents_after_rerank:
              print(f"== {doc['company']} (Relevance: {doc['relevance_score']:.4f})")

          return top_documents_after_rerank

      except Exception as e:
          print(f"An error occurred during re-ranking: {e}")
          return documents[:top_n]

    def format_documents_for_chat(self, documents: List[Dict]) -> List[Dict]:
      return [
        {
          "company": doc['company'],
          "combined_attributes": doc['combined_attributes']
        }
        for doc in documents
      ]

    def get_embedding(self, text: str, input_type: str="search_document") -> list[float]:
        if not text.strip():
            print("Attempted to get embedding for empty text.")
            return []

        model = "embed-english-v3.0"
        response = self.co.embed(
            texts=[text],
            model=model,
            input_type=input_type, # Used for embeddings of search queries run against a vector DB to find relevant documents
            embedding_types=['float'],
        )

        return response.embeddings.float[0]
    
    def vector_search(self, user_query, filters, collection):
        """
        Perform a vector search in the MongoDB collection based on the user query.

        Args:
        user_query (str): The user's query string.
        collection (MongoCollection): The MongoDB collection to search.

        Returns:
        list: A list of matching documents.
        """

        # Generate embedding for the user query
        query_embedding = self.get_embedding(user_query, input_type="search_query")

        if query_embedding is None:
            return "Invalid query or embedding generation failed."

        # Define the vector search pipeline
        vector_search_stage = {
            "$vectorSearch": {
            "index": "vector_index",
            "queryVector": query_embedding,
            "path": "embedding",
            "numCandidates": 150,  # Number of candidate matches to consider
            "limit": 5,  # Return top 4 matches,
            "filter" : filters 
            }
        }

        # print("Vector search stage:", vector_search_stage)

        unset_stage = {
            "$unset": "embedding"  # Exclude the 'embedding' field from the results
        }

        project_stage = {
            "$project": {
            "_id": 0,  # Exclude the _id field
            "company": 1,  # Include the plot field
            "reports": 1,  # Include the title field
            "combined_attributes": 1, # Include the genres field
            "score": {
                "$meta": "vectorSearchScore"  # Include the search score
            }
            }
        }

        pipeline = [vector_search_stage, unset_stage, project_stage]

        # Execute the search
        results = collection.aggregate(pipeline)
        return list(results)

    def send_message(self, message: str, filters: dict, vector_search_func) -> any:
      self.add_to_history(message, "USER")
      yield("*Thinking...*\n\n\n")
      yield("*Fetching relevant docs from MongoDB Atlas...*\n\n\n")

      # Perform vector search
      search_results = vector_search_func(message, filters, self.collection)
      # Rerank the search results
      yield("*Reranking search results using Cohere...*\n\n\n")
      reranked_documents = self.rerank_documents(message, search_results)

      # Format documents for chat
      formatted_documents = self.format_documents_for_chat(reranked_documents)
      # print("formatted_docs", formatted_documents)
      if formatted_documents == []:
         yield("There are no stocks that match the criteria, please choose different filters.")
      else :
        # Generate response using Cohere chat
        response = self.co.chat_stream(
          chat_history=self.get_chat_history(),
          message=self.system + message,
          documents=formatted_documents,
          model="command-r-plus",
          temperature=0.3
        )
        for chunk in response:
          if(chunk.event_type=="text-generation"):
              yield(chunk.text) 
          elif(chunk.event_type=="citation-generation"):
             print("Citation generation")
             break
          
    def show_history(self):
      history = self.history_collection.find({'session_id': self.session_id}).sort('_id', 1)
      for item in history:
        print(f"{item['prefix']}: {item['message']}")
        print("-------------------------")