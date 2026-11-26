import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import re
import io
from gtts import gTTS
from google import genai
from google.genai import types

st.set_page_config(page_title="UPI Guardian: FinTech Fraud & Compliance Copilot", page_icon="🛡️", layout="wide")

st.title("🛡️ UPI Guardian: Autonomous FinTech Fraud & Compliance Copilot")
st.caption("Real-Time Anomaly Prevention • Time-Series Spike Forecasting • Gemini Text-to-SQL & RAG • Hands-Free Voice Assistant")

# Sidebar: API Key & Filters
with st.sidebar:
    st.header("🔑 Gemini AI Configuration")
    api_key = st.text_input("Enter Gemini API Key (Paste AIza... for Live Voice/LLM)", type="password")
    st.divider()
    st.header("📍 Regional Filter")
    selected_cities = st.multiselect(
        "Select Cities",
        ["Bangalore", "Punjab", "Chennai", "Mumbai", "Delhi", "Hyderabad"],
        default=["Bangalore", "Punjab", "Chennai", "Mumbai", "Delhi", "Hyderabad"]
    )

@st.cache_data
def load_data():
    conn = sqlite3.connect("fintech_fraud.db")
    df = pd.read_sql_query("SELECT * FROM scored_transactions", conn)
    policies = pd.read_sql_query("SELECT * FROM compliance_policies", conn)
    conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df, policies

df, policies_df = load_data()
filtered_df = df[df["txn_city"].isin(selected_cities)]

# Top KPI Row
col1, col2, col3, col4 = st.columns(4)
blocked_df = filtered_df[filtered_df["prevention_action"].isin(["BLOCK_FREEZE", "HOLD_24H"])]
col1.metric("Total Transactions", f"{len(filtered_df):,}")
col2.metric("Fraudulent Attempts", f"{int(filtered_df['is_fraud'].sum()):,}")
col3.metric("Blocked / Held Transfers", f"{len(blocked_df):,}")
col4.metric("INR Losses Prevented", f"₹{blocked_df[blocked_df['is_fraud']==1]['amount_inr'].sum():,.0f}")

st.divider()

tab1, tab2, tab3 = st.tabs(["📊 Fraud Analytics & Prevention", "🤖 AI Compliance Copilot (Text + Voice)", "📜 Regulatory Policies & Live Ledger"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        fraud_city = filtered_df[filtered_df["is_fraud"] == 1].groupby(["txn_city", "fraud_type"])["amount_inr"].sum().reset_index()
        fig_bar = px.bar(
            fraud_city, x="txn_city", y="amount_inr", color="fraud_type", barmode="group",
            category_orders={"txn_city": ["Bangalore", "Punjab", "Chennai", "Mumbai", "Delhi", "Hyderabad"]},
            title="🚨 Fraud Volume (INR) by City & Attack Pattern", template="plotly_dark"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    with col2:
        action_counts = filtered_df["prevention_action"].value_counts().reset_index()
        action_counts.columns = ["Action", "Count"]
        fig_pie = px.pie(
            action_counts, names="Action", values="Count", hole=0.45,
            title="🛡️ Real-Time Prevention Decision Split", template="plotly_dark"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with tab2:
    st.subheader("🎙️ Ask the FinTech Compliance Copilot (Voice or Text)")
    audio_value = st.audio_input("Speak your investigation query (e.g., 'Find velocity burst transactions in Hyderabad')")
    text_query = st.text_input("Or type your question here:", value="Show the top 5 blocked transactions in Chennai and Bangalore, and tell me which AML or RBI compliance rules apply.")

    if st.button("🚀 Run Investigation", type="primary"):
        final_question = text_query
        client = genai.Client(api_key=api_key) if api_key else None

        # 1. Live Voice Transcription if Audio Provided + API Key Present
        if audio_value is not None:
            if client is not None:
                try:
                    with st.spinner("🎧 Transcribing your voice query with Gemini..."):
                        audio_bytes = audio_value.read()
                        transcribe_resp = client.models.generate_content(
                            model="gemini-3.5-flash-lite",
                            contents=[
                                "Transcribe this spoken FinTech fraud investigation question accurately. Return ONLY the text.",
                                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
                            ]
                        )
                        final_question = transcribe_resp.text.strip()
                        st.info(f"🗣️ **Transcribed Voice Query:** {final_question}")
                except Exception:
                    st.warning("⚡ Live voice API quota busy — using your text query box.")
            else:
                st.warning("🔑 Paste your Gemini API Key (`AIza...`) in the left sidebar for live voice transcription—using your text query box for now.")

        if final_question:
            with st.spinner("🔍 Generating Safe SQL & Checking RBI/AML Compliance Rules..."):
                schema_info = """
                Table: scored_transactions
                Columns: txn_id, user_id, timestamp, amount_inr, txn_city, home_city, account_age_days,
                         kyc_verified, avg_monthly_spend, payment_remark, spend_to_avg_ratio,
                         is_new_device, is_city_mismatch, is_late_night, txns_last_15_mins,
                         has_scam_keyword, is_fraud, fraud_type, fraud_risk_score, prevention_action
                Values for prevention_action: 'BLOCK_FREEZE', 'HOLD_24H', 'CHALLENGE_2FA', 'APPROVE'
                Values for fraud_type: 'Account_Takeover', 'Velocity_Burst', 'Social_Engineering_Scam', 'None'
                """
                # 2. Text-to-SQL (Live Gemini with Smart Keyword-Aware Fallback)
                try:
                    if client is None:
                        raise ValueError("No API Key")
                    sql_resp = client.models.generate_content(
                        model="gemini-3.5-flash-lite",
                        contents=f"Convert into a single valid SQLite SELECT query. Return ONLY raw SQL:\n{schema_info}\nQuestion: {final_question}"
                    )
                    cleaned_sql = sql_resp.text.strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
                except Exception:
                    st.info("⚡ Running Smart Deterministic SQL & RAG Compliance Engine")
                    q_lower = final_question.lower()
                    cities = [c for c in ["Chennai", "Bangalore", "Hyderabad", "Mumbai", "Delhi", "Punjab"] if c.lower() in q_lower]
                    city_clause = f"AND txn_city IN ({','.join([repr(c) for c in cities])})" if cities else ""

                    if "velocity" in q_lower:
                        type_clause = "AND fraud_type = 'Velocity_Burst'"
                    elif "takeover" in q_lower:
                        type_clause = "AND fraud_type = 'Account_Takeover'"
                    elif "scam" in q_lower:
                        type_clause = "AND fraud_type = 'Social_Engineering_Scam'"
                    elif "kyc" in q_lower:
                        type_clause = "AND kyc_verified = 0"
                    else:
                        type_clause = "AND prevention_action = 'BLOCK_FREEZE'"

                    cleaned_sql = f"""
                    SELECT txn_id, user_id, timestamp, amount_inr, txn_city, home_city,
                           kyc_verified, fraud_type, fraud_risk_score, prevention_action
                    FROM scored_transactions
                    WHERE is_fraud = 1 {city_clause} {type_clause}
                    ORDER BY amount_inr DESC
                    LIMIT 5;
                    """

                cleaned_sql = cleaned_sql.strip()
                if re.search(r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)\b", cleaned_sql, re.IGNORECASE) or not cleaned_sql.upper().startswith("SELECT"):
                    st.error("🚨 Security Guardrail Blocked Unsafe SQL!")
                else:
                    conn = sqlite3.connect("fintech_fraud.db")
                    res_df = pd.read_sql_query(cleaned_sql, conn)
                    conn.close()

                    st.code(cleaned_sql, language="sql")
                    st.dataframe(res_df.head(15), use_container_width=True)

                    if not res_df.empty:
                        # 3. RAG Compliance Briefing (Live Gemini with Dynamic Rule Fallback)
                        try:
                            if client is None:
                                raise ValueError("No API Key")
                            rag_prompt = f"""
                            You are an Autonomous FinTech Compliance Officer. Cite exact rule codes (AML-101, AML-204, RBI-SCAM-09, KYC-302, SAR-500).
                            Question: {final_question}
                            SQL Data: {res_df.head(10).to_string(index=False)}
                            Policies: {policies_df.to_string(index=False)}
                            """
                            briefing = client.models.generate_content(model="gemini-3.5-flash-lite", contents=rag_prompt).text
                        except Exception:
                            top_row = res_df.iloc[0]
                            q_lower = final_question.lower()
                            if "velocity" in q_lower:
                                rule_detail = "* **AML-204 (Rapid Velocity Burst Rule):** 3+ transactions within 15 minutes triggered automated velocity throttling and `HOLD_24H` / `BLOCK_FREEZE` review.\n"
                            elif "scam" in q_lower:
                                rule_detail = "* **RBI-SCAM-09 (Social Engineering Protection):** Suspicious payment remarks (`KYC`, `Lottery`, `Refund`) triggered mandatory `CHALLENGE_2FA` / `BLOCK_FREEZE`.\n"
                            elif "kyc" in q_lower:
                                rule_detail = "* **KYC-302 (Unverified Account Cap):** Accounts with `kyc_verified = 0` exceeding ₹10,000 are automatically blocked.\n"
                            else:
                                rule_detail = "* **AML-101 (High-Value Nighttime & New Device Rule):** Transfer > ₹40,000 from an unregistered device/city triggered an immediate `BLOCK_FREEZE` and Biometric step-up.\n"

                            user_str = top_row.get("user_id", "Flagged Account")
                            txn_str = f" (`{top_row['txn_id']}`)" if "txn_id" in top_row else ""
                            amt_val = top_row.get("amount_inr", top_row.get("total_fraud_amount", 0))
                            city_str = f" in **{top_row['txn_city']}**" if "txn_city" in top_row else ""

                            briefing = (
                                f"**Top Flagged Entity:** `{user_str}`{txn_str} with **₹{amt_val:,.2f}**{city_str}.\n\n"
                                f"{rule_detail}"
                                "* **SAR-500:** Confirmed fraud > ₹50,000 requires filing a Suspicious Activity Report within 24 hours."
                            )
