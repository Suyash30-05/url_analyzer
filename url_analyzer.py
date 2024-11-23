import streamlit as st
from groq import Groq
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    TooManyRequests,
    TranslationLanguageNotAvailable,
    NoTranscriptAvailable,
    NotTranslatable,
    TranscriptsDisabled,
    InvalidVideoId
)
from urllib.parse import urlparse, parse_qs
import re
import math

# Define available Groq models with their details
GROQ_MODELS = {
    "mixtral-8x7b-32768": {
        "name": "Mixtral 8x7B-32K",
        "description": "Best for complex tasks, largest context window",
        "max_tokens": 32768,
        "suggested_temp": 0.3
    },
    "llama2-70b-4096": {
        "name": "LLaMA2 70B",
        "description": "Powerful general-purpose model",
        "max_tokens": 4096,
        "suggested_temp": 0.7
    },
    "gemma-7b-it": {
        "name": "Gemma 7B",
        "description": "Fast and efficient for simple tasks",
        "max_tokens": 8192,
        "suggested_temp": 0.7
    }
}


from urllib.parse import urlparse, parse_qs
import re

def setup_page():
    st.set_page_config(
        page_title="Content Summarizer",
        page_icon="📝",
        layout="wide"
    )
    
    st.title("📝 Smart Content Summarizer")
    st.markdown("""
    Get concise summaries of web articles and YouTube videos using Groq's LLM.
    Just paste a URL and let AI do the magic! ✨
    """)

def get_groq_client(api_key):
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        st.error(f"Error initializing Groq client: {str(e)}")
        return None

def extract_youtube_id(url):
    try:
        # Handle various YouTube URL formats
        parsed_url = urlparse(url)
        
        # Handle youtu.be format
        if parsed_url.hostname in ('youtu.be', 'www.youtu.be'):
            return parsed_url.path[1:]
            
        # Handle youtube.com format
        if parsed_url.hostname in ('youtube.com', 'www.youtube.com'):
            if parsed_url.path == '/watch':
                query_params = parse_qs(parsed_url.query)
                if 'v' in query_params:
                    return query_params['v'][0]
                    
        # Handle shortened URLs
        if parsed_url.path.startswith('/shorts/'):
            return parsed_url.path.split('/shorts/')[1]
            
        return None
    except Exception as e:
        st.error(f"❌ Error parsing YouTube URL: {str(e)}")
        return None

def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([item['text'] for item in transcript_list])
        
    except VideoUnavailable:
        st.error("❌ The video is unavailable. It might be private or deleted.")
        return None
        
    except TooManyRequests:
        st.error("❌ Too many requests were made to YouTube. Please try again later.")
        return None
        
    except TranscriptsDisabled:
        st.error("❌ Transcripts are disabled for this video by the content creator.")
        return None
        
    except NoTranscriptFound:
        st.error("❌ No transcript was found for this video in the default language.")
        # Try to get available transcript languages
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            available_languages = [trans.language_code for trans in transcript_list]
            if available_languages:
                st.info(f"💡 Available transcript languages: {', '.join(available_languages)}")
        except Exception:
            pass
        return None
        
    except TranslationLanguageNotAvailable:
        st.error("❌ The requested translation language is not available.")
        return None
        
    except NoTranscriptAvailable:
        st.error("❌ No transcript is available for this video.")
        return None
        
    except NotTranslatable:
        st.error("❌ This transcript cannot be translated.")
        return None
        
    except InvalidVideoId:
        st.error("❌ The provided YouTube video ID is invalid.")
        return None
        
        
    except Exception as e:
        st.error(f"❌ An unexpected error occurred: {str(e)}")
        return None

def get_webpage_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            st.error("❌ URL does not point to a valid webpage. Please provide a web article URL.")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
            element.decompose()
            
        # Get text and clean it
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        if not text.strip():
            st.error("❌ No readable content found on the webpage.")
            return None
            
        return text
        
    except requests.exceptions.MissingSchema:
        st.error("❌ Invalid URL. Please include 'http://' or 'https://' in the URL.")
        return None
        
    except requests.exceptions.ConnectionError:
        st.error("❌ Could not connect to the website. Please check the URL and your internet connection.")
        return None
        
    except requests.exceptions.Timeout:
        st.error("❌ Request timed out. The website might be slow or unavailable.")
        return None
        
    except requests.exceptions.TooManyRedirects:
        st.error("❌ Too many redirects. The URL might be invalid or the website might be misconfigured.")
        return None
        
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ HTTP Error: {str(e)}")
        return None
        
    except Exception as e:
        st.error(f"❌ Error fetching webpage content: {str(e)}")
        return None

def split_into_chunks(text, max_tokens):
    # Approximate tokens (rough estimate: 4 characters per token)
    chars_per_chunk = max_tokens * 3
    
    # Split into sentences (basic implementation)
    sentences = re.split('(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_length = len(sentence)
        
        if current_length + sentence_length > chars_per_chunk:
            if current_chunk:  # If we have accumulated sentences
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:  # If single sentence is too long
                chunks.append(sentence[:chars_per_chunk])
        else:
            current_chunk.append(sentence)
            current_length += sentence_length
    
    # Add any remaining sentences
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def generate_chunk_summary(client, chunk, model_id, temperature, chunk_num, total_chunks):
    try:
        prompt = f"""
        This is part {chunk_num} of {total_chunks} of the content. Please provide a clear summary of this section.
        Use bullet points for key points and maintain context awareness.
        
        Content: {chunk}
        """
        
        completion = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "You are a professional content summarizer focusing on creating clear, contextual summaries of content sections."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=1000
        )
        
        return completion.choices[0].message.content
        
    except Exception as e:
        st.error(f"❌ Error generating summary for chunk {chunk_num}: {str(e)}")
        return None

def generate_final_summary(client, summaries, model_id, temperature):
    try:
        combined_summaries = "\n\n".join(summaries)
        
        prompt = f"""
        Below are summaries of different sections of a longer content. Please provide a well-structured, 
        coherent final summary that combines all these sections while maintaining the overall context and flow.
        Make sure to highlight the most important points and connections between different sections.

        Section Summaries:
        {combined_summaries}
        """
        
        completion = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "You are a professional content summarizer. Create a cohesive final summary that brings together multiple section summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=1500
        )
        
        return completion.choices[0].message.content
        
    except Exception as e:
        st.error(f"❌ Error generating final summary: {str(e)}")
        return None

def generate_summary(client, content, model_id, temperature):
    try:
        # Get model details
        model_info = GROQ_MODELS[model_id]
        max_tokens = model_info['max_tokens']
        
        # Calculate chunks needed
        content_length = len(content)
        chars_per_token = 3  # rough estimate
        estimated_tokens = content_length / chars_per_token
        
        # If content is small enough, process it directly
        if estimated_tokens <= (max_tokens / 2):
            prompt = f"""
            Please provide a detailed summary of the following content in a well-structured format.
            Format the summary with main points, key takeaways, and important details.
            Use markdown formatting for better readability.
            
            Content: {content}
            """
            
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are a professional content summarizer. Create well-structured, clear summaries using markdown formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=min(2000, max_tokens // 2)
            )
            
            return completion.choices[0].message.content, None
            
        else:
            # Split content into chunks
            chunks = split_into_chunks(content, max_tokens // 2)
            total_chunks = len(chunks)
            
            # Create progress bar
            progress_bar = st.progress(0)
            chunk_summaries = []
            
            # Process each chunk
            for i, chunk in enumerate(chunks):
                st.info(f"Processing chunk {i+1} of {total_chunks}...")
                chunk_summary = generate_chunk_summary(client, chunk, model_id, temperature, i+1, total_chunks)
                if chunk_summary:
                    chunk_summaries.append(chunk_summary)
                progress_bar.progress((i + 1) / total_chunks)
            
            # Generate final summary
            st.info("Generating final combined summary...")
            final_summary = generate_final_summary(client, chunk_summaries, model_id, temperature)
            
            return final_summary, chunk_summaries
            
    except Exception as e:
        st.error(f"❌ Error generating summary: {str(e)}")
        return None, None

def main():

    setup_page()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("🔑 Configuration")
        
        # API Key input
        api_key = st.text_input("Enter Groq API Key", type="password")
        
        # Model selection
        st.markdown("### 🤖 Model Selection")
        selected_model = st.selectbox(
            "Choose a model",
            options=list(GROQ_MODELS.keys()),
            format_func=lambda x: GROQ_MODELS[x]['name']
        )
        
        # Temperature slider
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=GROQ_MODELS[selected_model]['suggested_temp'],
            step=0.1,
            help="Higher values make the output more creative but less focused"
        )
        
        # # Display model information
        # display_model_info(selected_model)
        
        st.markdown("---")
        st.markdown("### 📌 Instructions")
        st.markdown("""
        1. Enter your Groq API key
        2. Select a model and adjust temperature
        3. Paste a URL (webpage or YouTube video)
        4. Click 'Generate Summary'
        """)
        
        st.markdown("---")
        st.markdown("### ℹ️ Supported URLs")
        st.markdown("""
        - Web articles
        - YouTube videos (with available transcripts)
        - YouTube Shorts
        """)
    
    # Main content area
    url = st.text_input("🔗 Enter URL (webpage or YouTube video)", 
                       placeholder="https://example.com or https://youtube.com/watch?v=...")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        process_button = st.button("Generate Summary", type="primary", use_container_width=True)
    with col2:
        show_raw = st.button("Show Raw Content", type="secondary", use_container_width=True)
    
    if process_button:
        if not api_key:
            st.warning("⚠️ Please enter your Groq API key in the sidebar.")
            return
            
        if not url:
            st.warning("⚠️ Please enter a URL.")
            return
            
        with st.spinner("🔄 Processing content..."):
            client = get_groq_client(api_key)
            if not client:
                return
                
            # Check if it's a YouTube URL
            video_id = extract_youtube_id(url)
            
            if video_id:
                st.info("📺 Processing YouTube video...")
                content = get_youtube_transcript(video_id)
            else:
                st.info("🌐 Processing webpage...")
                content = get_webpage_content(url)
                
            if content:
                st.info(f"🤖 Generating summary using {GROQ_MODELS[selected_model]['name']}...")
                final_summary, chunk_summaries = generate_summary(
                    client, content, selected_model, temperature
                )
                
                if final_summary:
                    st.success("✅ Summary generated successfully!")
                    
                    # Display model used for transparency
                    st.markdown(f"*Generated using {GROQ_MODELS[selected_model]['name']} (temperature: {temperature})*")
                    
                    # Display final summary
                    st.markdown("### 📝 Final Summary")
                    st.markdown(final_summary)
                    
                    # Display individual chunk summaries in an expander
                    if chunk_summaries:
                        with st.expander("View Section-by-Section Summaries"):
                            for i, chunk_summary in enumerate(chunk_summaries):
                                st.markdown(f"### Section {i+1}")
                                st.markdown(chunk_summary)
                                st.markdown("---")
                    
                    # Add download buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            label="📥 Download Final Summary",
                            data=final_summary,
                            file_name="final_summary.md",
                            mime="text/markdown"
                        )
                    
                    if chunk_summaries:
                        with col2:
                            all_summaries = "# Complete Summary Report\n\n"
                            all_summaries += "## Final Summary\n\n" + final_summary + "\n\n"
                            all_summaries += "## Section-by-Section Summaries\n\n"
                            for i, summary in enumerate(chunk_summaries):
                                all_summaries += f"### Section {i+1}\n\n" + summary + "\n\n---\n\n"
                            
                            st.download_button(
                                label="📥 Download Complete Report",
                                data=all_summaries,
                                file_name="complete_summary_report.md",
                                mime="text/markdown"
                            )
    
    # Show raw content if requested
    if show_raw and url:
        with st.spinner("🔄 Fetching content..."):
            video_id = extract_youtube_id(url)
            if video_id:
                content = get_youtube_transcript(video_id)
            else:
                content = get_webpage_content(url)
            
            if content:
                with st.expander("Raw Content"):
                    st.text_area("Content", value=content, height=300)
if __name__ == "__main__":
    main()