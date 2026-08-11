from lightning_sdk import Studio
s = Studio()
url = s.add_ports(8000)
print("Public URL:", url[0].urls[0] if url else "Failed")
