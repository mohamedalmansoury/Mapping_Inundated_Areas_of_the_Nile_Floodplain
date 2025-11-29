import ee

# Authenticate Earth Engine
print("Starting Earth Engine authentication...")
print("A browser window will open for you to authorize access.")
print("Please follow the instructions in the browser.")

ee.Authenticate()

print("\nAuthentication complete!")
print("You can now initialize Earth Engine with: ee.Initialize()")
