# extractor.py
# from config import 
from schema import UserInput, StructuredUserInput, Itinerary_Structure, DayStructure, ActivitySlot

def extract_user_input(raw: dict) -> UserInput:
    
    return UserInput(**raw)