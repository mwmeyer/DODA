from openai import AsyncOpenAI
import settings
import os 
import importlib
import json
import platform
import textwrap

import traceback

openai = AsyncOpenAI(api_key=settings.OPENAI_KEY)

class Conversation:
    """DODA conversation manager."""

    # llm_model: str = "gpt-3.5-turbo-0125"
    llm_model: str = "gpt-4-0125-preview"
    
    def generate_system_content(self):
        template_path = './internal/custom_instructions.txt'
        try:
            with open(template_path, 'r') as file:
                template = file.read()
            
            content = template.format(
                platform=platform.platform(),
                cwd=os.getcwd(),
                shell=os.environ['SHELL'],
                path=os.environ['PATH'],
                user=os.environ['USER']
                # Add more dynamic values as needed
            )
            return textwrap.dedent(content)
        except Exception as e:
            print(f"Error loading system content template: {e}")
            return ""

    def load_functions(self):
        """Load function configurations from JSON and dynamically import functions."""
        try:
            with open('./internal/functions.json', 'r') as file:
                self.tools = json.load(file)

            self.available_functions = {}
            self.functions_confirmation_required = ['run_command']
            for tool in self.tools:
                function_name = tool['function']['name']
                if os.environ.get('FUNCTION_CONFIRMATION_REQUIRED') != "false":
                    self.functions_confirmation_required.append(function_name)
                module_name = f"internal.functions.{function_name}"
                function_module = importlib.import_module(module_name)
                self.available_functions[function_name] = getattr(function_module, function_name)

        except Exception as e:
            print(f"Error loading functions: {e}")

    def __init__(self) -> None:
        self.messages: list[dict] = [
            {"role": "system", "content": self.generate_system_content().replace('\n', '').strip() },
        ]
        self.load_functions()
        # print("****self.available_functions", self.available_functions)
        self.pending_confirmation = False
        self.last_pending_message = None
    
    async def handle_confirmation(self, function_data, response_message):
        """Handle the creation of a confirmation dialog."""
        confirmation_dialog = f"🔧 I'm about to run {function_data.name}, args: {function_data.arguments}\n"
        confirmation_dialog += "To confirm, reply with: 'y'\n"
        confirmation_dialog += "To cancel, reply with: 'n'"
        self.pending_confirmation = True
        self.last_pending_message = response_message
        return confirmation_dialog

    async def process_tool_calls(self, tool_calls):
        """Process tool calls and append responses to self.messages."""
        print(f"ℹ️ process_tool_calls - tool_calls: {tool_calls}")
        function_response = None
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = self.available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)

            try:
                if not function_args:
                    function_response = function_to_call()
                else:
                    function_response = function_to_call(**function_args)
            except Exception as e:
                print(f"💥 process_tool_calls error: {str(e)}")
                print(traceback.format_exc())
                self.messages.pop() # rollback tool call
                return False
            self.messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": str(function_response),
            })
        return function_response

    async def generate_response(self, response_message):
        """Generate and handle the model's response."""
        second_response = await openai.chat.completions.create(model=self.llm_model,
        messages=self.messages)
        response_message = second_response.choices[0].message
        self.messages.append({"role": "assistant", "content": response_message.content})
        return response_message.content

    async def send(self, message: str) -> str:
        """Send a message to the chat and return choices."""
        collapsible_data = None
        if self.pending_confirmation:
            self.pending_confirmation = False
            if message.lower() == "y":
                self.pending_confirmation = False
                tool_call_status = await self.process_tool_calls(self.last_pending_message.tool_calls)
                if not tool_call_status:
                    response_content = "Sorry, I ran into an error while processing the tool call."
                else:
                    response_content = await self.generate_response(self.last_pending_message)
            else:
                # user didnt confirm, so lets rollback the last message
                self.messages.pop()
                response_content = "OK, what would you like to do instead?"
        else:
            self.messages.append({"role": "user", "content": message})
            response = await openai.chat.completions.create(model=self.llm_model,
            messages=self.messages,
            tools=self.tools,
            tool_choice="auto")
            response_message = response.choices[0].message

            if response_message.tool_calls:
                self.messages.append({"role": "assistant", "content": response_message.content, "tool_calls": response_message.tool_calls})
                function_name = response_message.tool_calls[0].function.name
                if function_name in self.functions_confirmation_required:
                    response_content = await self.handle_confirmation(response_message.tool_calls[0].function, response_message)
                    return { 'response_content': response_content }
                tool_call_function_response = await self.process_tool_calls(response_message.tool_calls)
                if not tool_call_function_response:
                    return "Sorry, I ran into an error while processing the tool call."
                if type(tool_call_function_response) is dict and tool_call_function_response.get('show_collapsible'):
                    collapsible_data = tool_call_function_response.get('output')
                response_content = await self.generate_response(response_message)
            else:
                self.messages.append({"role": "assistant", "content": response_message.content})
                response_content = response_message.content
        return { 'response_content': response_content, 'collapsible_data': collapsible_data }

    def clear(self) -> None:
        """Clear current conversation."""
        self.messages = []