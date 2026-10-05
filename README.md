# Time Clock - User Guide

**Time Clock** is a lightweight, easy-to-use desktop time tracking application designed to help you track your work hours across tasks, distinguish between reported and unreported time, and export your records for invoicing, payroll, or personal productivity analysis.

---

## Table of Contents
1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Managing Tasks](#managing-tasks)
4. [Tracking Time](#tracking-time)
5. [Editing Clock In/Out Times (Advanced)](#editing-clock-in-out-times-advanced)
6. [Managing Reported vs. Unreported Time](#managing-reported-vs-unreported-time)
7. [Viewing Session History](#viewing-session-history)
8. [Exporting Your Data](#exporting-your-data)
9. [Tips for Effective Time Tracking](#tips-for-effective-time-tracking)
10. [Frequently Asked Questions](#frequently-asked-questions)

---

## Getting Started

### Launching the Application
To start Time Clock, open your terminal in the application folder and run:
```bash
python3 main.py
```
The application window will open immediately. All your tasks, tracked sessions, and reporting history are saved automatically on your local machine so you never lose your progress.

---

## Interface Overview

The Time Clock window is organized into three intuitive areas:

```
+------------------------------------------------------------------------+
|  Top Menu: File | Advanced (Edit Task..., Delete Task...)              |
+------------------------------------+-----------------------------------+
|  Tasks Panel (Left)                |  Clock Tracker (Top Right)        |
|  - Add new tasks (Paid / Unpaid)   |  - Active task status & timer     |
|  - 💰 Paid status indicator column |  - All Tasks Summary: Day/Week/Mo |
|  - Select, rename, archive tasks   |  - Clock In / Clock Out button    |
|  - Unified Edit Task dialog        |  - Mark Reported button           |
|  - Show/hide archived tasks        |                                   |
|  - View total & unreported times   |                                   |
|                                    +-----------------------------------+
|                                    |  Session History (Bottom Right)   |
|                                    |  - Detailed session timestamps    |
|                                    |  - Reported vs unreported status  |
|                                    |  - Task history export & summary  |
+------------------------------------+-----------------------------------+
```

- **File Menu (Top Bar)**: Access global data export (CSV/JSON) and application exit.
- **Advanced Menu (Top Bar)**: Access tools to open the unified task editing dialog (**Edit Task...**) or permanently delete a selected task (**Delete Task...**).
- **Tasks Panel (Left Side)**: Manage your list of projects or tasks, view the `💰` paid status column, configure options, and switch between them.
- **Clock Tracker (Top Right)**: Control your live timer and see current session progress.
- **Session History (Bottom Right)**: Review logged work sessions for the selected task.

---

## Managing Tasks

The **Tasks** panel on the left allows you to organize your work into discrete tasks or projects.

### Paid vs. Unpaid Tasks
Tasks in Time Clock can be designated as either **Paid** (default) or **Unpaid**:
- **Paid (Reportable)**: Billable or client-facing tasks that accumulate unreported time as you work. Unreported time is tracked toward reporting milestones and highlighted when pending.
- **Unpaid (Non-reportable)**: Internal, non-billable, or administrative activities (e.g., internal meetings, breaks, learning). Unpaid tasks track total elapsed duration normally (contributing to task total time and Day, Week, and Month summaries) but always show `00:00:00` for Unreported Time and never appear as pending unreported work.
- **Visual Badges & Color Coding**: Unpaid tasks are clearly labeled with an `[Unpaid]` badge across the task list, active timer header, session history, and dialog dropdowns, and are visually distinguished in warm amber text.
- **Reporting Controls**: Because unpaid tasks do not accumulate reportable time, reporting actions (**Report...** in Tasks panel and **Mark Reported** in Clock Tracker) are automatically disabled when an unpaid task is selected.

### Task List & Unreported Time Indicators
The task table displays your tasks with a paid indicator column alongside their **Total Time** and **Unreported Time**:
- **Paid Indicator Column (`💰`)**: A dedicated column on the left displays a money emoji (`💰`) for paid tasks and remains blank for unpaid tasks, allowing you to instantly identify billable projects at a glance.
- **Visual Status Highlighting**: Paid tasks containing pending unreported time (`> 00:00:00`) are prominently highlighted in blue text so you can immediately see which projects need to be billed or submitted. Fully reported paid tasks appear in neutral dark text, unpaid tasks appear in distinct warm amber text, and archived tasks appear in muted gray.
- **Live Synchronization**: As you clock in, clock out, or track active work, the task's unreported time counter, paid indicator, and highlight tag update automatically in real time.
- **Aggregate Summary Indicator**: A footer summary below the task list displays the total number of projects with outstanding work and cumulative pending duration (e.g., `Unreported: 2 projects (04:15:00)`), ignoring unpaid tasks so your pending billing summary stays accurate.

### Adding a Task
1. Click the **New Task...** button at the top of the Tasks panel.
2. In the modal dialog:
   - Enter or paste the name of your task (e.g., `Client Website Redesign`, `Internal Sync`).
   - Select the task type: **Paid (Reportable)** or **Unpaid (Non-reportable)**.
3. Click **OK** or press **Enter / Return** on your keyboard.
4. Your new task appears in the task list below and is automatically selected.

### Selecting a Task
- Click on any task in the list to select it.
- Once selected, the **Clock Tracker** and **Session History** panels automatically update to show details for that task.

### Editing Task Options and Sessions (Unified Dialog)
You can change a task's name, toggle its paid/unpaid status, adjust active running timers, and edit past session records in a single unified dialog:
1. Click on the task in the list to select it.
2. Click the **Options...** button below the task list (or choose **Advanced -> Edit Task...** from the top menu bar).
3. In the unified dialog:
   - **Task Details & Options**:
     - Choose a task from the **Select Task** dropdown.
     - View and edit the full task name in the dedicated full-width **Task Name** field, providing ample space for long task names.
     - Toggle between **Paid (Reportable)** and **Unpaid (Non-reportable)** status, then click **Save Options**.
   - **Active Running Session**: If the task is running, edit the start timestamp and click **Apply Start Time**.
   - **Completed Sessions**: Select any historical session to modify start/end timestamps via **Save Changes**, or insert a missed session using **Add as New**.
4. The task list, timer panel, and session views will instantly update to reflect your changes.

### Renaming a Task
You can quickly rename a task directly:
1. Click on the task you wish to rename to highlight it.
2. Click the **Rename** button below the task list.
3. Enter the new name in the popup dialog and confirm.
4. The task list and timer header will immediately reflect the updated name.

### Archiving and Unarchiving Tasks
Archiving allows you to keep your active task list organized and focused without losing any tracked work sessions, total duration, or historical reporting metrics:
- **Archiving a Task**:
  1. Click on the task in the list that you wish to archive.
  2. Click the **Archive** button below the task list and confirm in the dialog prompt.
  3. The task is removed from the default active task list.
  4. If the task was actively clocked in when archived, the running session is automatically and safely finalized and saved.
  5. The application will automatically switch active selection to the next available unarchived task.
- **Viewing Archived Tasks**:
  - Check the **Show Archived** box at the top right of the Tasks panel.
  - Archived tasks will appear in the task list with an `[Archived]` tag and muted gray text.
- **Unarchiving a Task**:
  1. Enable the **Show Archived** checkbox.
  2. Click on the archived task you want to restore.
  3. The management button will dynamically change to **Unarchive**.
  4. Click **Unarchive** to restore the task to the active list.

### Deleting a Task
1. Click the task in the list that you wish to remove.
2. In the top application menu bar, click **Advanced** and select **Delete Task...**.
3. A confirmation dialog will ask if you are sure you want to delete the task and all of its recorded sessions.
4. Confirm to permanently remove the task.

---

## Tracking Time

The **Clock Tracker** panel in the upper right gives you full control over timing your active work sessions.

### Starting a Timer (Clock In)
1. Select the task you want to work on from the Tasks list.
2. Click the large **Clock In** button.
3. The display will change:
   - The status updates to **Status: Running (Clocked In)**.
   - The **Start Time** shows the exact time tracking began.
   - The large digital stopwatch begins counting up in `HH:MM:SS` (Hours:Minutes:Seconds).
   - The button label switches to **Clock Out**.

### Stopping a Timer (Clock Out)
1. When you pause or finish working on the task, click **Clock Out**.
2. The session ends, the timer resets to `00:00:00`, and the completed work interval is automatically saved to the **Session History** table.
3. Both **Total Time** and **Unreported Time** for the task update instantly.

### Aggregate Period Counters (Day, Week, Month)
Directly below the active task counters in the **Clock Tracker**, the **All Tasks Summary** displays your total cumulative hours across all tasks:
- **Day**: Total time logged today (starting from midnight 00:00:00 local time).
- **Week**: Total time logged during the current calendar week (starting Monday at 00:00:00).
- **Month**: Total time logged during the current calendar month (starting on the 1st of the month at 00:00:00).
- **Includes Archived Tasks**: Hours logged to archived projects are automatically included in Day, Week, and Month totals, ensuring your progress and timesheet totals remain completely accurate even when old tasks are archived.
- **Real-Time Ticking**: While clocked in, these period counters dynamically increment second-by-second alongside your active session.

### Persistent Running Timer on Exit
If you close the application window while a timer is running without clocking out, the clock continues running in the background. When you reopen Time Clock, your active session seamlessly resumes from where you left off, with your original start time and elapsed duration preserved.

---

## Editing Clock In/Out Times (Advanced)

If you forget to clock in on time, forget to clock out, or need to correct past timestamps, Time Clock provides a dedicated **Advanced** menu option.

### Opening the Edit Dialog
1. In the top application menu bar, click **Advanced**.
2. Select **Edit Task...**.
3. A modal dialog will appear centered over the application window.

### Selecting a Task and Editing Details
- Use the **Select Task** dropdown at the top to choose the task you wish to inspect or edit. It defaults to your currently selected task and includes any archived tasks.
- The **Task Name** is displayed on its own wide input line across the dialog width, making it convenient to read and edit long task names.
- Adjust the **Paid (Reportable)** or **Unpaid (Non-reportable)** classification and click **Save Options** to update task attributes.

### Adjusting an Active Session Start Time
If the selected task is currently clocked in:
1. The **Active Running Session** section will display your active clock-in timestamp.
2. Edit the **Start Time** field (e.g. adjust `2026-10-01 09:30:00` to `2026-10-01 09:00:00`).
3. Click **Apply Start Time**.
4. The live timer and total duration will update immediately across all panels.

### Editing Completed Session Records
1. In the **Completed Sessions** table, click on any past session to highlight and populate its timestamps into the edit fields below.
2. Modify the **Start** and/or **End** timestamp.
3. Click **Save Changes**.
4. The duration will automatically recompute, and your task totals and session history will refresh immediately.

### Adding a Missed Session Manually
1. Enter the desired **Start** and **End** timestamps in the input fields.
2. Click **Add as New**.
3. A new completed session entry is added to the task, and duration and period totals are recalculated automatically.

### Supported Timestamp Formats & Validation
- **Formats**: Supports standard ISO formats with or without the `T` separator (e.g., `2026-10-01 09:00:00` or `2026-10-01T09:00:00`).
- **Validation**:
  - Start timestamps cannot be set in the future.
  - End timestamps cannot be earlier than start timestamps.
  - Descriptive error messages are displayed if an invalid date or timestamp format is entered.

---

## Managing Reported vs. Unreported Time

When logging hours for client billing, contractor timesheets, or sprint reporting, you often need to know which hours have already been submitted and which hours remain unreported.

### Understanding Time Counters
- **Total Time**: The cumulative duration of all recorded sessions for the task.
- **Unreported Time**: The duration of work completed *after* your last reporting cutoff timestamp.

### Marking Time as Reported
Click the **Report...** button in the Tasks panel (or **Mark Reported** in the Clock Tracker panel) to access the reporting menu:

1. **Mark as Reported Now**:
   - Sets the cutoff timestamp to the current moment.
   - Marks all sessions completed up to this point as reported.
   - Resets the task's **Unreported Time** counter to zero while keeping the **Total Time** intact.

2. **Custom Timestamp...**:
   - Allows you to set a specific cutoff date and time in standard ISO format (`YYYY-MM-DDTHH:MM:SS`, e.g., `2026-10-01T17:00:00`).
   - Any sessions that ended at or before that timestamp will be marked as reported; sessions after that timestamp will remain unreported.

3. **Clear Reported Status**:
   - Clears the reporting cutoff for the task.
   - Returns all historical sessions to an unreported state, making your **Unreported Time** equal to your **Total Time**.

### Visual Indicators
- **Tasks List**:
  - Projects with pending unreported time (`> 00:00:00`) are highlighted in bold blue text with an aggregate unreported summary indicator in the footer.
  - Fully reported projects (`00:00:00`) appear in neutral muted text.
- **Session History Table**:
  - **Reported Sessions** are displayed in gray/dimmed text.
  - **Unreported Sessions** are displayed in normal, prominent text.

---

## Viewing Session History

The **Session History** panel in the lower right displays all individual work sessions for the currently selected task.

### Session Details Table
The history table lists each work interval with the following columns:
- **#**: Sequential session number.
- **Start Time**: Date and time the session began (`YYYY-MM-DD HH:MM:SS`).
- **End Time**: Date and time the session was stopped.
- **Duration**: Total elapsed time formatted as `HH:MM:SS`.

### History Summary Bar
The bottom footer displays a quick statistical breakdown for the active task:
- Total number of sessions logged.
- Total accumulated duration.
- Total unreported duration.

---

## Exporting Your Data

Time Clock offers flexible export options so you can easily analyze your data in spreadsheet software (such as Microsoft Excel, Google Sheets, or Apple Numbers) or integrate with other tools.

### 1. Exporting Single Task History
To export history for only the currently selected task:
1. Select the desired task from the Tasks list.
2. In the **Session History** panel, click the **Export...** button in the bottom left corner.
3. Choose your preferred file format:
   - **CSV (`.csv`)**: Ideal for spreadsheets. Includes task details, archive status, paid/unpaid (`is_unpaid`) status, start time, end time, and duration in seconds.
   - **JSON (`.json`)**: Ideal for technical workflows or importing into other tools.
4. Choose where to save the file and click **Save**.

### 2. Exporting All Application Data
To export all tasks (including active and archived projects) and all session records across the entire application at once:
1. Click the **File** menu in the top menu bar.
2. Select either:
   - **Export Data as CSV...**: Saves a comprehensive spreadsheet containing every task (with `is_archived` and `is_unpaid` status) and its complete session history.
   - **Export Data as JSON...**: Saves the complete application database in JSON format.
3. Select your destination folder and file name, then click **Save**.

---

## Tips for Effective Time Tracking

- **One Task at a Time**: Select a task before starting work to keep sessions categorized accurately.
- **Switching Tasks**: When switching projects, click **Clock Out** on the current task, select the new task in the left list, and click **Clock In**.
- **Weekly or Monthly Reporting**: At the end of each billing cycle or work week, use **Export Data as CSV...** to generate your timesheet report, then click **Mark as Reported Now** to start your next cycle with a clean unreported counter.
- **Accidental Exits**: Don't worry about losing running time if your computer restarts or the app is closed — active timers continue running and automatically resume when you reopen the application.

---

## Frequently Asked Questions

#### Where is my data stored?
Your data is stored locally in an embedded database file (`data/time_clock.db`) inside the application directory. No account creation or internet connection is required.

#### What happens if I forget to clock out?
If you leave a session running, you can clock out when you return. If you need to mark specific hours as already reported up to an earlier time, use **Report... -> Custom Timestamp...** to set the exact cutoff moment.

#### Can I export to Excel?
Yes! Export your data as a `.csv` file via the **File -> Export Data as CSV...** menu or the history **Export...** button. You can open `.csv` files directly in Microsoft Excel, Google Sheets, LibreOffice Calc, or Apple Numbers.
