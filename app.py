import gradio as gr

def fake_model(input_text):
    return f"Model processed: {input_text}"

demo = gr.Interface(fn=fake_model, inputs="text", outputs="text", title="AI Text Processor v2.1")

# HF expects port 7860
demo.launch(server_name="0.0.0.0", server_port=7860)
