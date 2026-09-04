from core.agentic_loop import JarvisBrain

brain = JarvisBrain()


def main():
  while True:
    user = input("\n[ Ask to Jarvis ]: ")

    if user.lower() == "quit":
      break 

    if not user:
      print("\nError: No input.")

    # Execution 
    response = brain.run(user_request=user)

    if response.status == "success":
      print(f"\nJarvis Response: \n{response.output}")

    else:
      print(f"\nError: \n{response.error}")

        
if __name__ == "__main__":
  main()