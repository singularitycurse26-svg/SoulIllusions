from lightning_sdk import Studio, Machine
s = Studio()
s.switch_machine(Machine.T4)
print("Switched to T4 GPU")
