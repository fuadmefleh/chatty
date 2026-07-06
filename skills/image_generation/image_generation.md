# Image Generation

## Description
Generates images from text prompts using OpenAI's `gpt-image-1` model. Use whenever the user
asks Chatty to create, draw, generate, or make a picture/image/illustration/photo of something.

## Usage
Call `generate_image` with a detailed prompt. It returns a URL to the generated image - embed it
directly in your reply as a markdown image (`![](<url>)`) so it renders inline in the chat.

## Examples
- "generate an image of a cat astronaut floating in space"
- "can you draw me a logo for a coffee shop called Ember?"
- "make a picture of a cozy cabin in the snow, portrait orientation"
