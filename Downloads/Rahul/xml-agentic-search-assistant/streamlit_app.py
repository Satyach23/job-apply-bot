import streamlit as st

from app.agents.rag_agent import answer_question
from app.storage import list_documents


def _init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_doc_id" not in st.session_state:
        st.session_state.selected_doc_id = None


def main() -> None:
    st.set_page_config(page_title="ACP Document Chatbot", layout="wide")
    _init_session()

    st.title("ACP Document Chatbot")
    st.write(
        "Ask questions about your uploaded documents. "
        "The agent will route metadata questions to SQLite and "
        "content questions to the vector store."
    )

    # Sidebar: document filter
    with st.sidebar:
        st.header("Document filter")
        docs = list_documents()
        options = ["All documents"] + [d["file_name"] for d in docs]
        choice = st.selectbox("Scope", options, index=0)
        if choice == "All documents":
            st.session_state.selected_doc_id = None
        else:
            idx = options.index(choice) - 1
            st.session_state.selected_doc_id = docs[idx]["id"]

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask about the law, sections, titles, etc."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        doc_id = st.session_state.selected_doc_id
        result = answer_question(prompt, doc_id)

        answer = result.get("answer", "No information found")
        source_type = result.get("source_type", "none")

        badge = ""
        if source_type == "metadata":
            badge = "\n\n_Source: SQLite (metadata)_"
        elif source_type == "content":
            badge = "\n\n_Source: Vector store (content)_"
        elif source_type == "both":
            badge = "\n\n_Source: SQLite + Vector store_"

        full_answer = answer + badge if badge else answer

        with st.chat_message("assistant"):
            st.markdown(full_answer)
        st.session_state.messages.append({"role": "assistant", "content": full_answer})


if __name__ == "__main__":
    main()

