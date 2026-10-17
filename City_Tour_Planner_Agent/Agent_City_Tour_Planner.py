"""
Agent - City Tour Planner
This is a sample program to implement the Tool calling, 
by using Langchain bind tools.
Agent 1 - Tavily Search Tool is used to find attractions in the city.
Agent 2 - Weather Tool is used to find the weather in the city.
Agent 3 - Tavily Search Tool is used to find the best restaurants in the city.
"""

from dotenv import load_dotenv
import os
import requests
import json
from langchain_tavily import TavilySearch
from langchain_groq import ChatGroq
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field
from langchain.tools import tool
import streamlit as st

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
Weather_api_key = os.getenv("Weather_api")
no_of_results = 5

class SearchResults_model(BaseModel):
    at_no: str = Field(..., description="Attraction number")
    at_content: str = Field(..., description="Attraction description")


@tool
def attractions_search(query:str) -> list:
    """Search for attractions in a city using Tavily Search tool."""
    search_tool=TavilySearch(max_results=no_of_results)
    result = search_tool.invoke(query)
    result_list = []
    for i in range(no_of_results):
        result_list.append(SearchResults_model(at_no=str(i+1), at_content=result["results"][i]["content"]))
    return result_list 

@tool
def restaurent_search(query:str) -> list:
    """Search for restaurants in a city using Tavily Search tool."""
    search_tool=TavilySearch(max_results=no_of_results)
    result = search_tool.invoke(query)
    result_list = []
    for i in range(no_of_results):
        result_list.append(SearchResults_model(at_no=str(i+1), at_content=result["results"][i]["content"]))
    return result_list 



@tool
def get_weather_data(city:str) -> str:
     """Fetch current weather information for a city!!!"
     """
     url = (
         f"https://api.weatherstack.com/current?"
         f"access_key={Weather_api_key}&query={city}"
     )

     response = requests.get(url)
     data = response.json()

     if "current" not in data:
         return "Weather data not found for the given city."
     else:
        return (
            f"City : {city} \n"
            f"Temperature : {data['current']['temperature']}°C\n"
            f"Description : {data['current']['weather_descriptions'][0]}\n"
            f"Humidity : {data['current']['humidity']}% "

        )
if __name__ == "__main__":
    #city = input("Enter the city name: ")
    st.set_page_config(page_title="City Tour Planner", page_icon="🏙️")
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(135deg, #e8f4f8 0%, #f4f7fb 55%, #fff4e8 100%);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title(" Agent : City Tour Planner 🏙 ️")
    st.subheader("Enter the city name to plan your tour:")
    city= st.text_area( "Enter the city name:",   
    placeholder="Toronto" )
    submit = st.button("Plan my tour", disabled=not city.strip())
    

    messages = [{
                        "role":"system",
                        "content":"You are a helpful tour planner.In your plan, include the top 5 attactions in the city, and  the top 5 restaurants in the city. Also, include the current weather information in the city. Plan the tour by using the available tools. Prepare your final output based on the tool results only. If the tool results do not contain enough information, say 'I don't know'.",
                    },
                    {
                        "role": "user",
                        "content": f"Plan a tour for {city}. ",
                    }]
    tool_names = {
                "attractions_search": attractions_search,
                "restaurent_search": restaurent_search,
                "get_weather_data": get_weather_data
            }

    if submit:
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")

        llm = ChatGroq(model="openai/gpt-oss-120b", api_key=GROQ_API_KEY).bind_tools(
            [attractions_search, restaurent_search, get_weather_data]
        )



        with st.spinner("Planning your city tour..."):
            max_round = 5
            conversation = messages
            for i in range(max_round):
                result = llm.invoke(conversation)
                conversation.append(result)

                if not result.tool_calls:
                    break

                for call in result.tool_calls:
                    tool_name = call["name"]
                    tool_result = tool_names[tool_name].invoke(call["args"])
                    conversation.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=call["id"],
                        name=tool_name,
                    ))

        st.markdown(result.content)