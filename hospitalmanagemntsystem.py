class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def introduce(self):
        print(f"Hello, my name is {self.name} and I am {self.age} years old.")

    def __str__(self):
        return f"{self.name}, {self.age} years old"


class Doctor(Person):
    def __init__(self, name, age, specialty, consultation_fee):
        super().__init__(name, age)
        self.specialty = specialty
        self.__consultation_fee = consultation_fee

    def examine(self):
        print(f"Dr. {self.name} is examining a patient in {self.specialty}.")

    def get_consultation_fee(self):
        return self.__consultation_fee

    def introduce(self):
        print(f"Hello, my name is {self.name} and I am {self.age} years old. Specialty: {self.specialty}")

    def __str__(self):
        return f"Dr. {self.name} ({self.specialty})"


class Patient(Person):
    def __init__(self, name, age, patient_id):
        super().__init__(name, age)
        self.patient_id = patient_id
        self._temperatures = []

    def add_temperature(self, temp):
        self._temperatures.append(temp)

    def get_average_temperature(self):
        if len(self._temperatures) == 0:
            return 0
        return sum(self._temperatures) / len(self._temperatures)

    def has_fever(self):
        return self.get_average_temperature() >= 37.5

    def introduce(self):
        print(f"Hello, my name is {self.name} and I am {self.age} years old. ID: {self.patient_id}")

    def __str__(self):
        fever_status = "Yes" if self.has_fever() else "No"
        return f"{self.name} (ID: {self.patient_id}) - Avg Temp: {self.get_average_temperature():.1f}°C - Fever: {fever_status}"


class Ward:
    def __init__(self, ward_number, doctor):
        self.ward_number = ward_number
        self.doctor = doctor
        self.patients = []

    def admit_patient(self, patient):
        self.patients.append(patient)

    def discharge_patient(self, patient_id):
        for patient in self.patients:
            if patient.patient_id == patient_id:
                self.patients.remove(patient)
                return

    def ward_average_temperature(self):
        if len(self.patients) == 0:
            return 0

        total = 0
        for patient in self.patients:
            total += patient.get_average_temperature()

        return total / len(self.patients)

    def display_info(self):
        print(f"=== Ward {self.ward_number} ===")
        print(f"Doctor: {self.doctor}")
        print()

        print("--- Introductions (polymorphism) ---")
        people = [self.doctor] + self.patients

        for person in people:
            person.introduce()

        print()
        print("Patients:")

        for patient in self.patients:
            print(patient)

    def __str__(self):
        return f"Ward {self.ward_number} has {len(self.patients)} patients and doctor {self.doctor.name}"


def find_highest_fever_patient(patients):
    return max(patients, key=lambda patient: patient.get_average_temperature())


def group_by_fever_status(patients):
    grouped = {
        "fever": [],
        "no_fever": []
    }

    for patient in patients:
        if patient.has_fever():
            grouped["fever"].append(patient.name)
        else:
            grouped["no_fever"].append(patient.name)

    return grouped


doctor1 = Doctor("Johnson", 45, "Cardiology", 500)

patient1 = Patient("Emma", 30, "P001")
patient1.add_temperature(38.0)
patient1.add_temperature(38.4)

patient2 = Patient("Liam", 25, "P002")
patient2.add_temperature(36.7)
patient2.add_temperature(36.9)

patient3 = Patient("Olivia", 40, "P003")
patient3.add_temperature(37.5)
patient3.add_temperature(37.7)

ward1 = Ward(204, doctor1)

ward1.admit_patient(patient1)
ward1.admit_patient(patient2)
ward1.admit_patient(patient3)

ward1.display_info()

print()
print(f"Ward Average Temperature: {ward1.ward_average_temperature():.1f}°C")

highest = find_highest_fever_patient(ward1.patients)
print(f"Highest Fever: {highest.name} ({highest.get_average_temperature():.1f}°C)")

grouped = group_by_fever_status(ward1.patients)
print(f"Grouped by fever: {grouped}")