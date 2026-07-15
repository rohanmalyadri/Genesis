try:
    print("Importing routes.query...")
    from routes.query import pipeline_step_1_guard
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
