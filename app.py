import streamlit as st
from backend import CohereChat

# Set page configuration to make sidebar non-collapsible
st.set_page_config(page_title="Stocks Recommender", initial_sidebar_state="expanded", layout="wide")

# Create tabs
tab1, tab2 = st.tabs(["Architecture Diagram", "Stock Recommender"])

with tab1:
    st.image("arch_diagram.png", caption="Architecture Diagram", use_column_width=True)
    pass

with tab2:
    # st.header("Stock Recommender")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.image("https://d1.awsstatic.com/awsi-fsi-partner-MongoDB.591f406ca71b4cd79ff0dbc7b9a258dac994a8e0.png", width=130)
    with col2:
        st.image("https://awsmp-logos.s3.amazonaws.com/87af0c85-6cf9-4ed8-bee0-b40ce65167e0/87cfe52d919e14913565a89247bebc5a.png", width=130)

    # Sidebar title
    st.sidebar.markdown("---")
    st.sidebar.title("Filters")

    # Market Cap Range
    apply_market_cap = st.sidebar.checkbox("Apply Market Cap Filter")
    if apply_market_cap:
        st.sidebar.header("Market Cap Range (in billion USD)")
        market_cap_filter = st.sidebar.selectbox("Choose Market Cap Range", ["Small-Cap ($300M - $2B)", "Mid-Cap ($2B - $10B)", "Large-Cap ($10B+)"])
        market_cap_dict = {}
        if market_cap_filter == "Small-Cap ($300M - $2B)":
            market_cap_dict = {"$gt": 0.3, "$lt": 2}
        elif market_cap_filter == "Mid-Cap ($2B - $10B)":
            market_cap_dict = {"$gt": 2, "$lt": 10}
        elif market_cap_filter == "Large-Cap ($10B+)":
            market_cap_dict = {"$gt": 10}

    # P/E Ratio Filter
    apply_pe_ratio = st.sidebar.checkbox("Apply P/E Ratio Filter")
    if apply_pe_ratio:
        st.sidebar.header("P/E Ratio")
        p_e_ratio_filter = st.sidebar.selectbox("Select P/E Ratio Range", ["10-15", "15-30", "30+"])
        p_e_ratio_dict = {}
        if p_e_ratio_filter == "10-15":
            p_e_ratio_dict = {"$gt": 10, "$lt": 15}
        elif p_e_ratio_filter == "15-30":
            p_e_ratio_dict = {"$gt": 15, "$lt": 30}
        elif p_e_ratio_filter == "30+":
            p_e_ratio_dict = {"$gt": 30}

    # Dividend Yield Filter
    apply_dividend_yield = st.sidebar.checkbox("Apply Dividend Yield Filter")
    if apply_dividend_yield:
        st.sidebar.header("Dividend Yield")
        dividend_yield_filter = st.sidebar.selectbox("Select Dividend Yield Range", ["0-2%", "2%+"])
        dividend_yield_dict = {}
        if dividend_yield_filter == "0-2%":
            dividend_yield_dict = {"$gt": 0, "$lt": 2}
        elif dividend_yield_filter == "2%+":
            dividend_yield_dict = {"$gt": 2}

    # Stock Price Filter
    apply_stock_price = st.sidebar.checkbox("Apply Stock Price Filter")
    if apply_stock_price:
        st.sidebar.header("Stock Price")
        stock_price_filter = st.sidebar.slider("Select Stock Price Range", 0, 1000, (50, 500), step=50, format="$%d")
        stock_price_dict = {"$gt": stock_price_filter[0], "$lt": stock_price_filter[1]}

    # Initialize CohereChat
    with open("system_prompt.txt", "r") as file:
        system_prompt = file.read()

    chat = CohereChat(
        system=system_prompt
    )

    # Input for user message
    col1, col2 = st.columns([5, 1])

    with col1:
        user_message = st.text_input(label="", label_visibility="collapsed", placeholder="Enter your query here")

    with col2:
        button = st.button("Ask")
        
    if button:
        if user_message.strip():
            try:
                filters = {"$or": []}
                if apply_market_cap:
                    filters["$or"].append({"key_metrics.market_cap": market_cap_dict})
                if apply_pe_ratio:
                    filters["$or"].append({"key_metrics.p_e_ratio": p_e_ratio_dict})
                if apply_dividend_yield:
                    filters["$or"].append({"key_metrics.dividend_yield": dividend_yield_dict})
                if apply_stock_price:
                    filters["$or"].append({"key_metrics.current_stock_price": stock_price_dict})

                if not filters["$or"]:
                    filters = {}

                print("filters", filters)
                with st.chat_message("ai"):
                    response = chat.send_message(user_message, filters, chat.vector_search)
                    st.write_stream(response)
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("Please enter a message.")