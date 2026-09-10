from core.agentic_loop import JarvisBrain

brain = JarvisBrain()


def main():
  while True:

    try:
      user = input("\n[ Ask to Jarvis ]: ")

      if user.lower() == "quit":
        memory_result = brain.end_session()
        if memory_result.error:
          print(f"\nEpisodic memory error: {memory_result.error}")
        for indexing_error in memory_result.indexing_errors:
          print(f"\nEpisodic memory indexing warning: {indexing_error}")
        break 

      if not user:
        print("\nError: No input.")

    except KeyboardInterrupt:
      print("\nTerminated")
      break
      
    # Execution 
    response = brain.run(user_request=user)

    if response.status == "success":
      print(
        f"\nJarvis Response: \n{response.output}"
        f"\nRuntime State: \n{response.state}"
      )

    else:
      print(f"\nError: \n{response.error}")

        
if __name__ == "__main__":
  main()