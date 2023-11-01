from netmiko import ConnectHandler
import re
import time
import datetime
from tkinter import *
from tkinter import ttk
from tkinter import messagebox
import sys
import threading
import csv
from statistics import mean
# Create GUI window and setup variables
win = Tk()
win.title('BTDRS')

patched_list = []
open_list = []
inttime = datetime.datetime.now()
strtime = str(datetime.datetime.now())
month = inttime.strftime("%b")
day = inttime.strftime("%d")
hour = inttime.strftime("%H")
strmin = inttime.strftime("%M")
outputfile = "BTDR" + "-" + "Output" + "_" + month + "-" + day + "_" + hour + "-" + strmin + ".csv"
vheaderlabel = "Batch TDR Scrubber"
vtarlabel = "Target IP"
vdistlabel = 'ADL: (1.0)'
vuserlabel = "Username"
vpasslabel = "Password"
ratio = '0/0'
numo = 0
deno = 0
vstatus = "Ready"
hname = 'Hostname'
tdr_results = ''
compdist = 1
# Define function to call with the gui to run the program
def run_tdr():
    global ip
    global username
    global password
    global vstatus
    global status
    global patched_list
    global open_list
    global hname
    global deno
    global numo
    global tdr_results
    global compdist
    # Get data from Entry objects of the GUI
    ip = etarget.get()
    username = eusername.get()
    password = epassword.get()
    compdist = edist.get()
    if compdist == '':
        compdist = 1.0
    compdist = float(compdist)
    # Ask for confirmation and close if false.
    confir = messagebox.askokcancel(title="Confirmation", message='Are you sure?')
    if confir is False:
        sys.exit()
    else:
        # Create dictionary from user input for netmiko
        device = {
            "device_type": "cisco_ios",
            "ip": ip,  # Replace with your switch's IP address
            "username": username,
            "password": password,
        }

        # Disable editable elements of the gui while code is running
        etarget.configure(state=DISABLED)
        edist.configure(state=DISABLED)
        eusername.configure(state=DISABLED)
        epassword.configure(state=DISABLED)
        tdr_button.configure(state=DISABLED)
        win.update()

        # Connect to the device
        try:
            with ConnectHandler(**device) as ssh_conn:
                print("Connected to", device["ip"])
                hname = ssh_conn.find_prompt()[:-1]
                print(hname)
                # Gather ints we are interested in for TDR
                output = ssh_conn.send_command("show interfaces status | inc notconnect")
                # Save output of the same command to iterate over again with show commands
                output2 = output
                # Set pattern to look for everything before first space
                interface_pattern = re.compile("^\S*")
                deno = len(output.splitlines())
                numo = 0
                # Iterate over every line (which ends up being every nc interface)
                for line in output.splitlines():
                    # Get the interface from the output line
                    notconnect_interface = re.findall(interface_pattern, line)
                    if bool(re.search('trunk', line)) is False:
                        if bool(re.search('routed', line)) is False:
                            if bool(re.search("/0/", notconnect_interface[0])) is True:
                                intrf = ssh_conn.send_command(f"show interface {notconnect_interface[0]}")

                                if bool(re.search("SFP", intrf)) is False:
                                    if bool(re.search("media type is unknown", intrf)) is False:

                                        # Run cable test on that interface
                                        tdr_output = ssh_conn.send_command_timing(f"test cable-diagnostics tdr interface {notconnect_interface[0]}")
                                        print(f"Running TDR test on {notconnect_interface[0]} ...")
                                        vstatus = f"Running TDR test on {notconnect_interface[0]} ..."
                                    else:
                                        print(f"Skipping {notconnect_interface[0]} ... (Media type unknown)")
                                        vstatus = f"Skipping {notconnect_interface[0]} ... (Media type unknown)"
                                else:
                                    print(f"Skipping {notconnect_interface[0]} ... (Media contains SFP)")
                                    vstatus = f"Skipping {notconnect_interface[0]} ... (Media contains SFP)"
                            else:
                                print(f"Skipping {notconnect_interface[0]} ... (Slot is not 0)")
                                vstatus = f"Skipping {notconnect_interface[0]} ... (Slot is not 0)"
                        else:
                            print(f"Skipping {notconnect_interface[0]} ... (Int is routed)")
                            vstatus = f"Skipping {notconnect_interface[0]} ... (Int is routed)"
                    else:
                        print(f"Skipping {notconnect_interface[0]} ... (Int is Trunk)")
                        vstatus = f"Skipping {notconnect_interface[0]} ... (Int is Trunk)"

                    numo = numo + 1
                    present()

                # Sleep in between TDR and show incase device only has one nc int
                time.sleep(10)

                numo = 0
                # Iterate again over output for show tdr
                for line2 in output2.splitlines():
                    notconnect_interface = re.findall(interface_pattern, line2)
                    if bool(re.search('trunk', line2)) is False:
                        if bool(re.search('routed', line2)) is False:
                            if bool(re.search("/0/", notconnect_interface[0])) is True:
                                intrf = ssh_conn.send_command(f"show interface {notconnect_interface[0]}")
                                if bool(re.search("SFP", intrf)) is False:
                                    if bool(re.search("media type is unknown", intrf)) is False:
                                        tdr_results = ssh_conn.send_command(f"show cable-diagnostics tdr interface {notconnect_interface[0]}")
                                        print(f"Reading TDR test on {notconnect_interface[0]} ...")
                                        vstatus = f"Reading TDR test on {notconnect_interface[0]} ..."
                                        # Logic for identifying if pair length is 0 on all pairs
                                        dist_lst = re.findall("(?<=Pair [ABCD]     )...", tdr_results)
                                        if len(dist_lst) == 0:
                                            print('No Pair Distances found')
                                        else:

                                            sdist_lst = [s.strip() for s in dist_lst]
                                            if 'N/A' in sdist_lst:
                                                print('TDR with N/A results Skipping')
                                                patched_list.append(notconnect_interface[0] + ',' + "N/A")
                                            else:
                                                adist_lst = [int(i) for i in sdist_lst]
                                                fldist = mean(adist_lst)
                                                if fldist < compdist:
                                                    print(f'Average cable distance of {fldist} is less than ADL of {compdist} meters')
                                                    open_list.append(notconnect_interface[0] + ',' + str(fldist))
                                                else:
                                                    print(f'Average cable distance of {fldist} meters is greater or equal to ADL of {compdist} meters')
                                                    patched_list.append(notconnect_interface[0] + ',' + str(fldist))

                                    else:
                                        print(f"Skipping {notconnect_interface[0]} ... (Media type unknown)")
                                        vstatus = f"Skipping {notconnect_interface[0]} ... (Media type unknown)"
                                else:
                                    print(f"Skipping {notconnect_interface[0]} ... (Media contains SFP)")
                                    vstatus = f"Skipping {notconnect_interface[0]} ... (Media contains SFP)"
                            else:
                                print(f"Skipping {notconnect_interface[0]} ... (Slot is not 0)")
                                vstatus = f"Skipping {notconnect_interface[0]} ... (Slot is not 0)"
                        else:
                            print(f"Skipping {notconnect_interface[0]} ... (Int is routed)")
                            vstatus = f"Skipping {notconnect_interface[0]} ... (Int is routed)"
                    else:
                        print(f"Skipping {notconnect_interface[0]} ... (Int is Trunk)")
                        vstatus = f"Skipping {notconnect_interface[0]} ... (Int is Trunk)"

                    numo = numo + 1
                    present()

                else:
                    print('****************************************')
                    print("Batch TDR completed")
                    vstatus = "Batch TDR completed"
                    #status = Label(win, text=vstatus, bd=1, relief=SUNKEN, anchor=E)
                    present()

                    print('Available ports:  ')
                    # Create list of lists for writing columns
                    open_lstlst = []
                    pat_lstlst = []
                    for el in open_list:
                        sub = el.split()
                        open_lstlst.append(sub)
                    print(open_lstlst)

                    # Create list of lists for writing columns
                    print('Patched ports:  ')
                    for elm in patched_list:
                        subm = elm.split()
                        pat_lstlst.append(subm)
                    print(pat_lstlst)

                    csvhead = [hname]
                    # Create new csv file and write every list as a new row
                    with open("Available_" + hname + "_" + outputfile, 'w', newline='') as f:
                        author = csv.writer(f)
                        author.writerow(csvhead)
                        for row in open_lstlst:
                            author.writerow(row)
                    f.close()

                    # Create new csv file and write every list as a new row
                    with open("Patched_" + hname + "_" + outputfile, 'w', newline='') as f:
                        author = csv.writer(f)
                        author.writerow(csvhead)
                        for row in pat_lstlst:
                            author.writerow(row)
                    f.close()

                    # Create Final message
                    finmess = (f'Batch TDR Completed on all notconnect interfaces\n\n'
                               f'List of all available ethernet ports: \n\n'
                               f'{open_list}\n\n'
                               f'List of all patched down ethernet ports: \n\n'
                               f'{patched_list}\n\n'
                               f'Results have been saved to: \n\n'
                               f'Available-{outputfile}\n'
                               f'Patched-{outputfile}'
                               )

                    # Present Message and close
                    messagebox.showinfo('Completed', finmess)
                    sys.exit()

        except Exception as e:
            # Generic Error handling
            print("An error occurred:", str(e))
            vstatus = f'Error: {str(e)}'
            present()

# Create GUI objects for first presentation
headerlabel = Label(win, text=vheaderlabel)
tarlabel = Label(win, text=vtarlabel)
etarget = Entry(win, width=15)
distlabel = Label(win, text=vdistlabel)
edist = Entry(win, width=3)
userlabel = Label(win, text=vuserlabel)
eusername = Entry(win, width=15)
passlabel = Label(win, text=vpasslabel)
epassword = Entry(win, show="*", width=15)
hnamelbl = Label(win, text=hname, relief=GROOVE, anchor=E)
ratiolbl = Label(win, text=ratio, relief=GROOVE, anchor=E)
status = Label(win, text=vstatus,  relief=GROOVE, justify='center')

# Create button to run function with another thread to keep gui alive
tdr_button = ttk.Button(win, text="Run Batch TDR", command=threading.Thread(target=run_tdr).start)

# First Presentation GUI order
headerlabel.grid(row=0, column=0, columnspan=2, padx=15, pady=10)
tarlabel.grid(row=1, column=0)
etarget.grid(row=2, column=0, padx=15)
distlabel.grid(row=1, column=1)
edist.grid(row=2, column=1, padx=15)

userlabel.grid(row=3, column=0)
eusername.grid(row=4, column=0)
passlabel.grid(row=3, column=1)
epassword.grid(row=4, column=1, padx=20)
tdr_button.grid(row=5, column=0, columnspan=2, pady=10)
hnamelbl.grid(row=6, column=0, columnspan=2, sticky=W + E)
ratiolbl.grid(row=7, column=0, columnspan=2, sticky=W + E)
status.grid(row=8, column=0, columnspan=2, sticky=W + E)

# Present function for updated data
def present():
    # Bring in variables from main that may have changed.
    global vheaderlabel
    global vtarlabel
    global vuserlabel
    global vpasslabel
    global vstatus
    global deno
    global numo
    global hname

    ratio = str(numo), '/', str(deno)
    # Recreate objects with possibly updated variables
    headerlabel = Label(win, text=vheaderlabel)
    tarlabel = Label(win, text=vtarlabel)
    # etarget = Entry(win, width=15)
    distlabel = Label(win, text=vdistlabel)
    #edist = Entry(win, width=3)
    userlabel = Label(win, text=vuserlabel)
    # eusername = Entry(win, width=15)
    passlabel = Label(win, text=vpasslabel)
    # epassword = Entry(win, show="*", width=15)
    hnamelbl = Label(win, text=hname, relief=GROOVE, anchor=E)
    ratiolbl = Label(win, text=ratio, relief=GROOVE, anchor=E)
    status = Label(win, text=vstatus, relief=GROOVE, justify='center')

    # Present objects again to update
    headerlabel.grid(row=0, column=0, columnspan=2, padx=15, pady=10)
    tarlabel.grid(row=1, column=0)
    etarget.grid(row=2, column=0, padx=15)
    distlabel.grid(row=1, column=1)
    edist.grid(row=2, column=1, padx=15)
    userlabel.grid(row=3, column=0)
    eusername.grid(row=4, column=0)
    passlabel.grid(row=3, column=1)
    epassword.grid(row=4, column=1, padx=20)
    tdr_button.grid(row=5, column=0, columnspan=2, pady=10)
    hnamelbl.grid(row=6, column=0, columnspan=2, sticky=W + E)
    ratiolbl.grid(row=7, column=0, columnspan=2, sticky=W + E)
    status.grid(row=8, column=0, columnspan=2, sticky=W + E)
    win.update()

win.mainloop()
