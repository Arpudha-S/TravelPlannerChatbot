from werkzeug.security import generate_password_hash

hashed = generate_password_hash("Admin@2025")
print(hashed)