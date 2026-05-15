import gradio as gr

def process_data(input_text):
    # You can put your actual ML model logic here later!
    return f"Processed: {input_text} (Tailscale is running in the background!)"

# Create a simple web interface
demo = gr.Interface(
    fn=process_data,
    inputs="text",
    outputs="text",
    title="My ML Space",
    description="This is a standard Hugging Face ML frontend."
)

# Bind to 0.0.0.0 and port 7860 so Hugging Face can route to it
demo.launch(server_name="0.0.0.0", server_port=7860)
