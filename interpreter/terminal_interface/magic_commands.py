import json
import os
import subprocess
import time
import platform
import tempfile

from ..core.utils.system_debug_info import system_info
from .utils.count_tokens import count_messages_tokens
from .utils.display_markdown_message import display_markdown_message

programming_languages = {
    "python": ".py",
    "javascript": ".js",
    "java": ".java",
    "c": ".c",
    "c++": ".cpp",
    "c#": ".cs",
    "swift": ".swift",
    "kotlin": ".kt",
    "ruby": ".rb",
    "php": ".php",
    "html": ".html",
    "css": ".css",
    "typescript": ".ts",
    "go": ".go",
    "rust": ".rs",
    "perl": ".pl",
    "shell": ".sh",
    "objective-c": ".m",
    "r": ".r",
    "scala": ".scala",
    "haskell": ".hs",
    "lua": ".lua",
    "dart": ".dart",
    "groovy": ".groovy",
    "matlab": ".m",
    "sql": ".sql",
    "assembly": ".asm",
    "fortran": ".f",
    "vbscript": ".vbs",
    "powershell": ".ps1",
    "racket": ".rkt",
    "clojure": ".clj"
}


def handle_undo(self, arguments):
    # Removes all messages after the most recent user entry (and the entry itself).
    # Therefore user can jump back to the latest point of conversation.
    # Also gives a visual representation of the messages removed.

    if len(self.messages) == 0:
        return
    # Find the index of the last 'role': 'user' entry
    last_user_index = None
    for i, message in enumerate(self.messages):
        if message.get("role") == "user":
            last_user_index = i

    removed_messages = []

    # Remove all messages after the last 'role': 'user'
    if last_user_index is not None:
        removed_messages = self.messages[last_user_index:]
        self.messages = self.messages[:last_user_index]

    print("")  # Aesthetics.

    # Print out a preview of what messages were removed.
    for message in removed_messages:
        if "content" in message and message["content"] != None:
            display_markdown_message(
                f"**Removed message:** `\"{message['content'][:30]}...\"`"
            )
        elif "function_call" in message:
            display_markdown_message(
                f"**Removed codeblock**"
            )  # TODO: Could add preview of code removed here.

    print("")  # Aesthetics.


def handle_help(self, arguments):
    commands_description = {
        "%% [commands]": "Run commands in system shell",
        "%verbose [true/false]": "Toggle verbose mode. Without arguments or with 'true', it enters verbose mode. With 'false', it exits verbose mode.",
        "%reset": "Resets the current session.",
        "%undo": "Remove previous messages and its response from the message history.",
        "%save_message [path]": "Saves messages to a specified JSON path. If no path is provided, it defaults to 'messages.json'.",
        "%load_message [path]": "Loads messages from a specified JSON path. If no path is provided, it defaults to 'messages.json'.",
        "%tokens [prompt]": "EXPERIMENTAL: Calculate the tokens used by the next request based on the current conversation's messages and estimate the cost of that request; optionally provide a prompt to also calulate the tokens used by that prompt and the total amount of tokens that will be sent with the next request",
        "%help": "Show this help message.",
        "%info": "Show system and interpreter information",
        "%edit": "Edit the last code"
    }

    base_message = ["> **Available Commands:**\n\n"]

    # Add each command and its description to the message
    for cmd, desc in commands_description.items():
        base_message.append(f"- `{cmd}`: {desc}\n")

    additional_info = [
        "\n\nFor further assistance, please join our community Discord or consider contributing to the project's development."
    ]

    # Combine the base message with the additional info
    full_message = base_message + additional_info

    display_markdown_message("".join(full_message))


def handle_verbose(self, arguments=None):
    if arguments == "" or arguments == "true":
        display_markdown_message("> Entered verbose mode")
        print("\n\nCurrent messages:\n")
        for message in self.messages:
            message = message.copy()
            if message["type"] == "image" and message.get("format") != "path":
                message["content"] = (
                    message["content"][:30] + "..." + message["content"][-30:]
                )
            print(message, "\n")
        print("\n")
        self.verbose = True
    elif arguments == "false":
        display_markdown_message("> Exited verbose mode")
        self.verbose = False
    else:
        display_markdown_message("> Unknown argument to verbose command.")


def handle_info(self, arguments):
    system_info(self)


def handle_reset(self, arguments):
    self.reset()
    display_markdown_message("> Reset Done")


def default_handle(self, arguments):
    display_markdown_message("> Unknown command")
    handle_help(self, arguments)


def handle_save_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "w") as f:
        json.dump(self.messages, f, indent=2)

    display_markdown_message(f"> messages json export to {os.path.abspath(json_path)}")


def handle_load_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "r") as f:
        self.messages = json.load(f)

    display_markdown_message(
        f"> messages json loaded from {os.path.abspath(json_path)}"
    )


def handle_count_tokens(self, prompt):
    messages = [{"role": "system", "message": self.system_message}] + self.messages

    outputs = []

    if len(self.messages) == 0:
        (conversation_tokens, conversation_cost) = count_messages_tokens(
            messages=messages, model=self.llm.model
        )
    else:
        (conversation_tokens, conversation_cost) = count_messages_tokens(
            messages=messages, model=self.llm.model
        )

    outputs.append(
        (
            f"> Tokens sent with next request as context: {conversation_tokens} (Estimated Cost: ${conversation_cost})"
        )
    )

    if prompt:
        (prompt_tokens, prompt_cost) = count_messages_tokens(
            messages=[prompt], model=self.llm.model
        )
        outputs.append(
            f"> Tokens used by this prompt: {prompt_tokens} (Estimated Cost: ${prompt_cost})"
        )

        total_tokens = conversation_tokens + prompt_tokens
        total_cost = conversation_cost + prompt_cost

        outputs.append(
            f"> Total tokens for next request with this prompt: {total_tokens} (Estimated Cost: ${total_cost})"
        )

    outputs.append(
        f"**Note**: This functionality is currently experimental and may not be accurate. Please report any issues you find to the [Open Interpreter GitHub repository](https://github.com/KillianLucas/open-interpreter)."
    )

    display_markdown_message("\n".join(outputs))

def handle_edit(self, arguments):
    lang = 'python'
    code = ''
    for i in self.messages[::-1]:
        if i["type"] == 'code':
            lang = i['format']
            code = i['content']

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=programming_languages[lang.lower()]) as temp_file:
        temp_file.write(code)
        temp_file.seek(0)  
        temp_filename = temp_file.name

    try:
        if platform.system() == 'Windows':
            os.system(f'start notepad {temp_filename}')
        elif platform.system() == 'Darwin':
            subprocess.call(('open', temp_filename))
        elif platform.system() == 'Linux':
            subprocess.call(('xdg-open', temp_filename))
        else:
            print(f"Unsupported OS: {platform.system()}")
    except Exception as e:
        print(f"Error opening file: {e}")

    input("Press Enter when you have finished editing...")

    with open(temp_filename, 'r') as modified_file:
        modified_code = modified_file.read()

    os.remove(temp_filename)

    self.messages.append({'role': 'assistant', 'type': 'code', 'format': lang, 'content': modified_code})


def handle_magic_command(self, user_input):
    # Handle shell
    if user_input.startswith("%%"):
        code = user_input[2:].strip()
        self.computer.run("shell", code, stream=True, display=True)
        print("")
        return

    # split the command into the command and the arguments, by the first whitespace
    switch = {
        "help": handle_help,
        "verbose": handle_verbose,
        "reset": handle_reset,
        "save_message": handle_save_message,
        "load_message": handle_load_message,
        "undo": handle_undo,
        "tokens": handle_count_tokens,
        "info": handle_info,
        "edit": handle_edit
    }

    user_input = user_input[1:].strip()  # Capture the part after the `%`
    command = user_input.split(" ")[0]
    arguments = user_input[len(command) :].strip()

    if command == "debug":
        print(
            "\n`%debug` / `--debug_mode` has been renamed to `%verbose` / `--verbose`.\n"
        )
        time.sleep(1.5)
        command = "verbose"

    action = switch.get(
        command, default_handle
    )  # Get the function from the dictionary, or default_handle if not found
    action(self, arguments)  # Execute the function
