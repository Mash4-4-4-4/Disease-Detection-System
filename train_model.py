
import os
print("Current working directory:", os.getcwd())

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn import svm
from sklearn.metrics import accuracy_score
import pickle

data=pd.read_csv(r'C:\Users\DELL\Downloads\diabetes.csv', encoding='latin1')

x=data.drop(columns='Outcome',axis=1)
y=data['Outcome']

scaler=StandardScaler()
scaleddata=scaler.fit_transform(x)
X=scaleddata
Y=y

X_train,X_test,Y_train,Y_test=train_test_split(X,Y,test_size=0.2,stratify=Y,random_state=2)

classifier=svm.SVC(kernel='linear')
classifier.fit(X_train,Y_train)

x_prediction=classifier.predict(X_train)
score=accuracy_score(x_prediction,Y_train)
print(score*100)


with open("diabetesmodel.pkl", "wb") as model_file:
    pickle.dump(classifier, model_file)

with open("scaler.pkl", "wb") as scaler_file:
    pickle.dump(scaler, scaler_file)

print("✅ Model and scaler saved successfully!")
