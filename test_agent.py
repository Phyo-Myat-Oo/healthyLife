from agent import run_health_agents
try:
    print(run_health_agents("I want to build muscle, I live in New York, and I am 25."))
except Exception as e:
    import traceback
    traceback.print_exc()
