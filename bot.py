# في دالة handle_text:
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=user_text,
    config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
)

# وفي دالة handle_photo:
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(data=bytes(image_bytes), mime_type="image/jpeg"),
        caption
    ],
    config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
)
