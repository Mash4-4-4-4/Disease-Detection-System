import numpy as np
import pickle

# --- Load model ---
with open("diabetesmodel.pkl", "rb") as model_file:  # <-- rb = read binary
    model = pickle.load(model_file)

# --- Load scaler ---
with open("scaler.pkl", "rb") as scaler_file:  # <-- rb = read binary
    scaler = pickle.load(scaler_file)

# --- Example input ---
# (Pregnancies, Glucose, BloodPressure, SkinThickness, Insulin, BMI, DiabetesPedigree, Age)
input_data = (6, 93, 50, 30, 64, 28.7, 0.356, 23)

# Convert to numpy array and reshape for a single sample
data_array = np.asarray(input_data).reshape(1, -1)

# --- Scale the input ---
scaled_data = scaler.transform(data_array)

# --- Predict ---
prediction = model.predict(scaled_data)

# --- Show result ---
print("✅ Result:", "Diabetic" if prediction[0] == 1 else "Not Diabetic")
