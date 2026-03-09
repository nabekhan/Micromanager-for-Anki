## **Micromanager for Anki**

**Micromanager** is a productivity enforcement add-on designed to eliminate distractions by locking you into your Anki study sessions until a specific goal is met. It employs aggressive "focus-yanking" and window management to ensure you don't stray from your decks.

Inspiration: https://ankiweb.net/shared/info/1356589749 and https://getcoldturkey.com/micromanager/

Loved FocusForce but it was buggy and didnt do everything I needed it to. Given that it has not been updated in a while I went ahead and made numerous changes. Please message me if you want this removed.

Code: https://github.com/nabekhan/Micromanager-for-Anki/tree/main

---

### **Core Functionality**

When an enforcement session is active, Micromanager implements the following restrictions:

* **Focus Enforcement**: If you click away from Anki or try to minimize the window, the app will automatically maximize and bring itself back to the front.
* **Deck Locking**: You are restricted to the specific deck you started with. Attempting to navigate to other decks will force you back to the deck browser or your original session.
* **Menu Blocking**: Access to the **Add-ons** menu is disabled during an active session to prevent you from simply turning off the add-on to escape.
* **Anti-Exit**: Standard close events are intercepted; you cannot close Anki normally until the goal is achieved or a bypass password is entered.

---

### **Lock Methods**

You can choose how difficult it is to "break" a session early:

* **Unlocked**: Allows you to abort the session after a simple confirmation prompt.
* **Locked**: The most restrictive mode. There is no password bypass; you **must** complete the goal to unlock Anki.
* **Random Text**: Generates a 200-character string of random symbols and letters. You must type this string perfectly (with no copy-pasting allowed) to unlock early.
* **Custom Password**: Requires a user-defined password to end the session.

---

### **Goal Types**

Sessions can be configured based on four distinct targets:

* **Total Reviews**: Complete a specific number of card reviews.
* **Correct Answers**: Stay locked in until you have answered a specific number of cards correctly.
* **Time (Minutes)**: A countdown timer that unlocks once the allotted time has expired.
* **Daily Reviews**: Locks you in until all currently due reviews in the selected deck are cleared.

---

### **Keyboard Shortcuts**

* **`Ctrl + Shift + M`**: Opens the Micromanager settings menu to start or update a session.

---

### **User Interface**

While a session is active, a persistent Heads-Up Display (HUD) appears at the top of the reviewer:

* **Progress Bar**: Visually tracks how close you are to your goal.
* **Status Label**: Shows your current count (e.g., "15 CARDS LEFT" or "05:00 TIMER").
* **Quick Actions**: Includes a settings icon to adjust the current session and an "X" button to attempt an early unlock.

