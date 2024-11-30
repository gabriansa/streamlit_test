import streamlit as st
import pandas as pd
from collections import deque
from datetime import datetime
import multiprocessing as mp
from time import sleep
import os

def generate_data(queue, stop_event, pause_event, counter):
    """
    Data generation process that runs independently.
    Removed all Streamlit dependencies from this function.
    """
    while not stop_event.is_set():
        if not pause_event.is_set():
            # Only increment and generate data if not paused
            with counter.get_lock():
                counter.value += 1
                step = counter.value
            
            data = {
                'timestamp': datetime.now().isoformat(),  # Convert to string for serialization
                'step': step,
                'pid': os.getpid()
            }
            queue.put(data)
            sleep(2)  # Simulate work
        else:
            sleep(0.1)  # Small sleep when paused to prevent busy waiting

def initialize_session_state():
    """
    Initialize all session state variables in one place
    """
    if 'initialized' not in st.session_state:
        st.session_state.data_queue = mp.Queue()
        st.session_state.stop_event = mp.Event()
        st.session_state.pause_event = mp.Event()
        st.session_state.counter = mp.Value('i', 0)
        st.session_state.local_data = deque()
        st.session_state.process = None
        st.session_state.running = False
        st.session_state.initialized = True

def main():
    # Page config
    st.set_page_config(page_title="Async Dashboard")
    
    # Initialize session state
    initialize_session_state()
    
    st.title("Async Dashboard")

    # Control buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button('Start', disabled=st.session_state.running):
            if st.session_state.process is None or not st.session_state.process.is_alive():
                # Clear events
                st.session_state.stop_event.clear()
                st.session_state.pause_event.clear()
                
                # Start new process
                st.session_state.process = mp.Process(
                    target=generate_data,
                    args=(
                        st.session_state.data_queue,
                        st.session_state.stop_event,
                        st.session_state.pause_event,
                        st.session_state.counter
                    )
                )
                st.session_state.process.start()
                st.session_state.running = True

    with col2:
        if st.button('Pause', disabled=not st.session_state.running):
            if st.session_state.pause_event.is_set():
                st.session_state.pause_event.clear()  # Resume
            else:
                st.session_state.pause_event.set()    # Pause

    with col3:
        if st.button('Clear', disabled=not (len(st.session_state.local_data) > 0 or st.session_state.running)):
            # Stop the process
            if st.session_state.process and st.session_state.process.is_alive():
                st.session_state.stop_event.set()
                st.session_state.process.join()
            
            # Clear all data
            st.session_state.local_data.clear()
            with st.session_state.counter.get_lock():
                st.session_state.counter.value = 0
            
            # Reset process state
            st.session_state.process = None
            st.session_state.running = False
            
            # Clear the queue
            while not st.session_state.data_queue.empty():
                try:
                    st.session_state.data_queue.get_nowait()
                except:
                    pass

    with col4:
        if len(st.session_state.local_data) > 0:
            current_df = pd.DataFrame(list(st.session_state.local_data))
            st.download_button(
                label="Download CSV",
                data=current_df.to_csv(index=False),
                file_name="data.csv",
                mime="text/csv"
            )

    # Check for new data from the queue
    if st.session_state.running:
        while not st.session_state.data_queue.empty():
            try:
                new_data = st.session_state.data_queue.get_nowait()
                # Convert ISO string back to datetime for display
                new_data['timestamp'] = datetime.fromisoformat(new_data['timestamp'])
                st.session_state.local_data.append(new_data)
            except:
                pass

    # Display data
    if len(st.session_state.local_data) > 0:
        current_df = pd.DataFrame(list(st.session_state.local_data))
        st.dataframe(current_df, use_container_width=True)

    # Status display
    status_placeholder = st.empty()
    with status_placeholder.container():
        if st.session_state.running:
            status = "PAUSED" if st.session_state.pause_event.is_set() else "RUNNING"
            st.write(f"Status: {status} | Steps: {len(st.session_state.local_data)}")
        else:
            st.info('Click "Start" to begin.')

    # Rerun to update UI
    if st.session_state.running:
        time_to_wait = 0.1 if st.session_state.pause_event.is_set() else 2
        sleep(time_to_wait)
        st.rerun()

if __name__ == '__main__':
    main()
