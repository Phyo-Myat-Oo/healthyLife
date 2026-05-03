# --- A Helper Function to Run Our Agents ---
# We'll use this function throughout the notebook to make running queries easy.

async def run_agent_query(agent: Agent, query: str, session: Session, user_id: str, is_router: bool = False):
    """Initializes a runner and executes a query for a given agent and session."""
    print(f"\n🚀 Running query for agent: '{agent.name}' in session: '{session.id}'...")

    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name=agent.name
    )

    final_response = ""
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=Content(parts=[Part(text=query)], role="user")
        ):
            if event.is_final_response():
                final_response = event.content.parts[0].text
    except Exception as e:
        final_response = f"An error occurred: {e}"

    if not is_router:
     print("\n" + "-"*50)
     print("✅ Final Response:")
     display(Markdown(final_response)) # output. can be delted this part and response only .
     print("-"*50 + "\n")

    return final_response

# --- Initialize our Session Service ---
# This one service will manage all the different sessions in our notebook.
session_service = InMemorySessionService()
my_user_id = "user-123"



#########################
# Agent #
gymselection_agent = Agent(
    name='gymselection_agent',
    model="gemini-2.5-flash",
    description="""A specialized geographic decision-agent that selects the optimal gym
    based on proximity to a user and quality of peer reviews. Use this
    agent when you have a list of location options and need to find the
    most convenient, high-rated facility""",

    instruction="""
    You are a Location Intelligence Specialist for a workout planning system.

    Your task:
    1. Receive a list of 10 gym locations, each including their coordinates/address and user reviews.
    2. Receive the user's current location.
    3. Calculate or determine which gym is geographically closest to the user.
    4. If two gyms are at a similar distance, use the reviews (rating and sentiment) as a tie-breaker to recommend the better-quality option.

    Output Format:
    Return ONLY the name and address of the chosen gym, followed by a one-sentence justification explaining why it was selected (e.g., 'This is the closest option and maintains a 4.5-star rating').
  """
)
async def gym_agent_tool(location_query: str):
    """
    Finds and evaluates gyms near a specific location. 
    Use this when a user asks for gym recommendations or locations.
    """
    # 1. Create a fresh session for this specific search
    sub_session = await session_service.create_session(
        app_name=gymselection_agent.name, 
        user_id=my_user_id
    )
    
    # 2. Run the sub-agent
    # is_router=True ensures we don't get the "✅ Final Response" UI clutter
    response = await run_agent_query(
        agent=gymselection_agent,
        query=f"Find and evaluate gyms in {location_query}. Focus on rating and user reviews.",
        session=sub_session,
        user_id=my_user_id,
        is_router=True 
    )
    
    return response

workout_planner_agent = Agent(
    name='workout_planner_agent',
    model="gemini-2.5-flash",
    description="Creates personalized workout regimes based on biological data and lifestyle factors.",
    tools=[gym_agent_tool], 
    instruction="""
    You are an expert Certified Strength and Conditioning Specialist (CSCS).
    
    Your goal is to create a 7-day workout plan based on the following user inputs:
    - Biological: Age, Sex, Weight, Height (BMI), Target Weight.
    - Lifestyle: Activity Level (Sedentary/Active), Sleep/Wake patterns.
    - Constraints: Budget (Money) and Health Conditions.
    
    Rules:
    1. If the user mentions health conditions, adapt the intensity and exercises (e.g., 'no heavy squats for back pain').
    2. Adjust volume based on sleep—if a user sleeps < 6 hours, suggest lower intensity to aid recovery.
    3. If the user query implies they need a place to work out or mentions 'where', 'location', or 'near me', 
       DELEGATE to the 'gymselection_agent'.
    
    Output Format:
    - Summary of the user's current status (BMI calculation, etc.)
    - Weekly Schedule (Day 1 - Day 7)
    - Nutrition Tip based on Target Weight.
    """
)
# Force clear any old coroutine objects
workout_planner_agent_session = None 

# 1. Create the session (ensure 'await' is used)
workout_planner_agent_session = await session_service.create_session(
    app_name=workout_planner_agent.name, 
    user_id=my_user_id
)

# 2. Run the query
await run_agent_query(
    agent=workout_planner_agent,
    query=structured_prompt,
    session=workout_planner_agent_session,
    user_id=my_user_id
)
# --- Diet Plan Agent ---

# A tool to signal that the loop should terminate
COMPLETION_PHRASE = "The meal meets all nutritional constraints."

def exit_loop(tool_context: ToolContext):
  """Call this function ONLY when the meal is approved, signaling the loop should end."""
  print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
  tool_context.actions.escalate = True
  return {}

# Agent 1: Proposes an initial meal (Has Search)
meal_finder_agent = Agent(
    name="meal_finder_agent",
    model="gemini-2.5-flash",
    tools=[google_search],
    instruction="""Taske the input for target marcro for each day and recommend a 1 day meal plan for breakfast, lunch, dinner
    Constraint: {{processed_constraints}}""",
    output_key="meal_plan"
)

# Agent 2 (in loop): Critiques the meal against macros (No Tools)
critic_agent = Agent(
    name="critic_agent",
    model="gemini-2.5-flash",
    tools=[exit_loop],
    instruction=f"""You are a strict, robotic nutritionist. Evaluate the current meal against the user's prompt.
    Original Request: {{session.query}}
    Current Meal: {{meal_plan}}
    If the meal does not meet the macro targets perfectly, provide a brief critique of what is missing (e.g., 'Protein is 20g short. Add 1 scoop of pea protein.').
    If the meal MEETS the targets, you MUST immediately call the 'exit_loop' tool.""",
    output_key="criticism"
)

# Agent 3 (in loop): Refines the meal based on critique or exits (Only Custom Tool)
refiner_agent = Agent(
    name="refiner_agent",
    model="gemini-2.5-flash",
    instruction=f"""You are a strict dietary modifier.
    Critique: {{criticism}}

    ELSE, generate a new meal string that incorporates the critique.
    DO NOT be conversational. Output ONLY the new string: 'Meal: [Updated Name], Macros: [Updated Macros]'.""",
    output_key="meal_plan"
)

# ✨ The LoopAgent orchestrates the meal evaluation cycle ✨
meal_refinement_loop = LoopAgent(
    name="meal_refinement_loop",
    sub_agents=[critic_agent, refiner_agent],
    max_iterations=2
)

# Agent 4: Schedules the approved meal
schedule_planner_agent = Agent(
    name="schedule_planner_agent",
    model="gemini-2.5-flash",
    instruction="""Take the final meal plan and format it nicely into a schedule.
    Final Meal: {{meal_plan}}"""
)

# ✨ The SequentialAgent puts it all together ✨
iterative_diet_workflow = SequentialAgent(
    name="iterative_diet_workflow",
    sub_agents=[meal_finder_agent, meal_refinement_loop, schedule_planner_agent],
    description="A workflow that finds, iteratively refines to hit macro goals, and schedules a meal plan for 1 days."
)

## Main Agent

medical_agent = Agent(
    name="medical_agent",
    model="gemini-2.5-flash",
    instruction="""
    Act as a Clinical Nutrition & Fitness Architect. Your task is to take my personal data (Age, Weight, Goals, Health Conditions, and Schedule) and transform it into a standardized processed_constraints block.

    Output Requirements:

    Calculate TDEE and Macros based on my profile.

    Convert health conditions into specific 'Dietary Filters' (e.g., Hypertension = Low Sodium).

    Map my sleep schedule to a 'Timing Window' (8:30 AM start, ending 3 hours before sleep).

    Identify 'Restricted Exercises/Meals' based on any injuries or medical history.

    Strict Format: You must output the result exactly in this Markdown structure:

    processed_constraints =
    Daily Target Profile:
    Total Calories: [X] kcal
    Macro Split: [P]g Protein / [C]g Carbs / [F]g Fat
    Dietary Filters: [List here]
    Timing Window: [Times here]
    Activity Context: [Workout priority here]
    Restricted Exercises: [List]
    Restricted Meals: [List]
    Allergies: [List]
    Injuries: [List]
    """,
    output_key="processed_constraints"
)

workout_plan_agent = Agent(
    name="workout_plan_agent",
    model="gemini-2.5-flash",
    instruction="""Create a workout plan for 1 day using this constraints: {{processed_constraints}}
    """,
    output_key="workout_plan"
)

parallel_plan_agent = ParallelAgent(
    name="parallel_plan_agent",
    sub_agents=[workout_plan_agent, iterative_diet_workflow]
)

final_plan_agent = Agent(
    name="final_agent",
    model="gemini-2.5-flash",
    instruction="""Take the final meal plan and workout plan and format it nicely into a schedule.
    Final Meal Plan: {{meal_plan}}
    Workout Plan: {{workout_plan}}"""
)

main_agent = SequentialAgent(
    name="main_agent",
    sub_agents=[parallel_plan_agent, final_plan_agent]
)

planner_agent = Agent(
    name="final_agent",
    model="gemini-2.5-flash",
    sub_agents=[main_agent]
)

# --- Corrected Agent Definitions ---

# A tool to signal that the loop should terminate
COMPLETION_PHRASE = "The meal meets all nutritional constraints."

def exit_loop(tool_context: ToolContext):
  """Call this function ONLY when the meal is approved, signaling the loop should end."""
  print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
  tool_context.actions.escalate = True
  return {}

# Agent 1: Proposes an initial meal (Has Search)
meal_finder_agent = Agent(
    name="meal_finder_agent",
    model="gemini-2.5-flash",
    tools=[google_search],
    instruction="""Taske the input for target marcro for each day and recommend a 1 day meal plan for breakfast, lunch, dinner""",
    output_key="meal_plan"
)

# Agent 2 (in loop): Critiques the meal against macros (No Tools)
critic_agent = Agent(
    name="critic_agent",
    model="gemini-2.5-flash",
    tools=[exit_loop],
    instruction=f"""You are a strict, robotic nutritionist. Evaluate the current meal against the user's prompt.
    Original Request: {{session.query}}
    Current Meal: {{meal_plan}}
    If the meal does not meet the macro targets perfectly, provide a brief critique of what is missing (e.g., 'Protein is 20g short. Add 1 scoop of pea protein.').
    If the meal MEETS the targets, you MUST immediately call the 'exit_loop' tool.""",
    output_key="criticism"
)

# Agent 3 (in loop): Refines the meal based on critique or exits (Only Custom Tool)
refiner_agent = Agent(
    name="refiner_agent",
    model="gemini-2.5-flash",
    instruction=f"""You are a strict dietary modifier.
    Critique: {{criticism}}

    ELSE, generate a new meal string that incorporates the critique.
    DO NOT be conversational. Output ONLY the new string: 'Meal: [Updated Name], Macros: [Updated Macros]'.""",
    output_key="meal_plan"
)

# ✨ The LoopAgent orchestrates the meal evaluation cycle ✨
meal_refinement_loop = LoopAgent(
    name="meal_refinement_loop",
    sub_agents=[critic_agent, refiner_agent],
    max_iterations=2
)

# Agent 4: Schedules the approved meal
schedule_planner_agent = Agent(
    name="schedule_planner_agent",
    model="gemini-2.5-flash",
    instruction="""Take the final meal plan and format it nicely into a schedule.
    Final Meal: {{meal_plan}}"""
)

# ✨ The SequentialAgent puts it all together ✨
iterative_diet_workflow = SequentialAgent(
    name="iterative_diet_workflow",
    sub_agents=[meal_finder_agent, meal_refinement_loop, schedule_planner_agent],
    description="A workflow that finds, iteratively refines to hit macro goals, and schedules a meal plan for 1 days."
)