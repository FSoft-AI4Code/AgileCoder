<script>
  import { onMount } from "svelte";
  import { Terminal } from "@xterm/xterm";
  import { FitAddon } from "@xterm/addon-fit";
  import { agentState } from "$lib/store";
  import { socket } from "$lib/api";
  import "@xterm/xterm/css/xterm.css";

  onMount(() => {
    const terminalBg = getComputedStyle(document.body).getPropertyValue("--terminal-window-background");
    const terminalFg = getComputedStyle(document.body).getPropertyValue("--terminal-window-foreground");

    const terminal = new Terminal({
      cursorBlink: true,
      convertEol: true,
      disableStdin: false,
      rows: 1,
      theme: {
        background: terminalBg,
        foreground: terminalFg,
        cursor: terminalFg,
        selectionForeground: terminalBg,
        selectionBackground: terminalFg
      }
    });

    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(document.getElementById("terminal-content"));
    fitAddon.fit();

    let inputBuffer = '';
    terminal.onKey(({ domEvent }) => {
      if (domEvent.ctrlKey && domEvent.code === 'KeyC') {
        navigator.clipboard.writeText(inputBuffer)
          .then(() => console.log("Copied to clipboard successfully!"))
          .catch(err => console.error("Failed to copy text: ", err));
        domEvent.preventDefault();
      } else if (domEvent.ctrlKey && domEvent.code === 'KeyV') {
        navigator.clipboard.readText()
          .then((clipText) => {
            inputBuffer += clipText;
            terminal.write(clipText);
          })
          .catch(err => console.error("Failed to read clipboard contents: ", err));
        domEvent.preventDefault();
      } else {
        handleNonClipboardKeys(domEvent);
      }
    });

    function handleNonClipboardKeys(domEvent) {
      if (domEvent.keyCode === 13) { // Enter key
        terminal.write('\r\n');
        terminal.write(`$ You typed: '${inputBuffer}'\r\n`);
        socket.emit("terminal_type", { data: inputBuffer });
        inputBuffer = '';
      } else if (domEvent.keyCode >= 32 && domEvent.keyCode !== 127) {
        inputBuffer += domEvent.key;
        terminal.write(domEvent.key);
      } else if (domEvent.keyCode === 8 && inputBuffer.length > 0) {
        inputBuffer = inputBuffer.slice(0, -1);
        terminal.write('\b \b');
      }
    }

    let previousState = {};

    agentState.subscribe((state) => {
      if (state && state.terminal_session) {
        let command = state.terminal_session.command || 'echo "Waiting..."';
        let output = state.terminal_session.output || "Waiting...";
        let title = state.terminal_session.title || "Terminal";

        if (command !== previousState.command || output !== previousState.output || title !== previousState.title) {
          if (title) {
            document.getElementById("terminal-title").innerText = title;
          }
          terminal.reset();
          terminal.write(`$ ${command}\r\n\r\n${output}\r\n`);
          previousState = { command, output, title };
        }
      } else {
        terminal.reset();
      }

      fitAddon.fit();
    });
  });
</script>
<!-- <script>
  import { onMount } from "svelte";
  import { Terminal } from "@xterm/xterm";
  import { FitAddon } from "@xterm/addon-fit";
  import { agentState } from "$lib/store";
  import { socket } from "$lib/api";
  import "@xterm/xterm/css/xterm.css";

  onMount(() => {
    const terminalBg = getComputedStyle(document.body).getPropertyValue("--terminal-window-background");
    const terminalFg = getComputedStyle(document.body).getPropertyValue("--terminal-window-foreground");

    const terminal = new Terminal({
      cursorBlink: true,
      convertEol: true,
      disableStdin: false,
      rows: 1,
      theme: {
        background: terminalBg,
        foreground: terminalFg,
        cursor: terminalFg,
        selectionForeground: terminalBg,
        selectionBackground: terminalFg
      }
    });

    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(document.getElementById("terminal-content"));
    fitAddon.fit();

    let inputBuffer = '';
    // terminal.onKey(({ key, domEvent }) => {
    //   if (domEvent.ctrlKey && key === 'v') {
    //     navigator.clipboard.readText().then(clipText => {
    //       inputBuffer += clipText;
    //       terminal.write(clipText);
    //     });
    //   } else if (domEvent.ctrlKey && key === 'c') {
    //     navigator.clipboard.writeText(inputBuffer);
    //   } else {
    //     handleNonClipboardKeys(key, domEvent);
    //   }
    // });
    terminal.onKey(({ key, domEvent }) => {
  if (domEvent.ctrlKey && (key === 'c' || key === 'C')) {
    navigator.clipboard.writeText(inputBuffer)
      .then(() => console.log("Copied to clipboard successfully!"))
      .catch(err => console.error("Failed to copy text: ", err));
    domEvent.preventDefault();  // Prevent the default behavior of the browser
  } else if (domEvent.ctrlKey && (key === 'v' || key === 'V')) {
    navigator.clipboard.readText()
      .then((clipText) => {
        inputBuffer += clipText;
        terminal.write(clipText);
      })
      .catch(err => console.error("Failed to read clipboard contents: ", err));
    domEvent.preventDefault();  // Prevent the default behavior of the browser
  } else {
    handleNonClipboardKeys(key, domEvent);
  }
}); 
    function handleNonClipboardKeys(key, domEvent) {
      domEvent.preventDefault(); // Prevent default browser handling

      if (domEvent.keyCode === 13) { // Enter key
        terminal.write('\r\n'); // Move to new line
        terminal.write(`$ You typed: '${inputBuffer}'\r\n`); // Display the buffer content
        socket.emit("terminal_type", { data: inputBuffer });
        inputBuffer = ''; // Clear the buffer after command execution
      } else if (domEvent.keyCode >= 32 && domEvent.keyCode !== 127) {
        inputBuffer += key; // Append printable character
      } else if (domEvent.keyCode === 8 && inputBuffer.length > 0) {
        inputBuffer = inputBuffer.slice(0, -1); // Handle backspace
      }

      // Always clear the line and redraw the input buffer
      terminal.write('\x1b[2K'); // Clear the line
      terminal.write('\r'); // Carriage return to the beginning of the line
      terminal.write(`$ ${inputBuffer}`); // Redraw the current input buffer
    }

    let previousState = {};

    agentState.subscribe((state) => {
      if (state && state.terminal_session) {
        let command = state.terminal_session.command || 'echo "Waiting..."';
        let output = state.terminal_session.output || "Waiting...";
        let title = state.terminal_session.title || "Terminal";

        if (command !== previousState.command || output !== previousState.output || title !== previousState.title) {
          if (title) {
            document.getElementById("terminal-title").innerText = title;
          }
          terminal.reset();
          terminal.write(`$ ${command}\r\n\r\n${output}\r\n`);
          previousState = { command, output, title };
        }
      } else {
        terminal.reset();
      }

      fitAddon.fit();
    });
  });
</script> -->



<div
  class="w-full h-full flex flex-col border-[3px] overflow-hidden rounded-xl border-window-outline"
>
  <div class="flex items-center p-2 border-b bg-terminal-window-ribbon">
    <div class="flex ml-2 mr-4 space-x-2">
      <div class="w-3 h-3 rounded-full bg-terminal-window-dots"></div>
      <div class="w-3 h-3 rounded-full bg-terminal-window-dots"></div>
      <div class="w-3 h-3 rounded-full bg-terminal-window-dots"></div>
    </div>
    <span id="terminal-title" class="text-tertiary text-sm">Terminal</span>
  </div>
  <div
    id="terminal-content"
    class="w-full h-full rounded-bl-lg bg-terminal-window-background "
  ></div>
</div>

<style>
  #terminal-content :global(.xterm) {
    padding: 10px;
  }
  #terminal-content :global(.xterm-screen) {
    width: 100% !important;

  }
  #terminal-content :global(.xterm-rows) {
    width: 100% !important;
    height: 100% !important;
    overflow-x: scroll !important;
    /* hide the scrollbar */
    scrollbar-width: none;
  }
</style>