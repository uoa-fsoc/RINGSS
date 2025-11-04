import numpy as np
import sys
import os
from pynput import keyboard
from datetime import datetime, timezone
import subprocess
import json
import glob
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

#Set paths
python = 'C:/Users/adamd/miniconda3/python.exe' #Absolute python.exe path
parameters_path = 'par-ardmore.json' #Relative parameters file path
data_path = 'C:/Users/adamd/Desktop/PHYSICS 789/RINGSS (local files)/Rings Processing/data' #Absolute main data folder path
outputs_path = os.path.abspath(os.path.join(data_path, '../outputs5')) #Get absolute output path from data path

#Set stop key
key_pressed = False

def on_space(key):
    global key_pressed
    
    try:
        if key.char == ' ': #Detect "space"
            key_pressed = True
            return False #Stop listener thread
    except AttributeError:
        pass #Ignore special keys, prevents crashes

#Start listener in a non-blocking way
listener = keyboard.Listener(on_press = on_space)
listener.start()
    
def continious_loop(object_name, hr): #Continously run script ("space" to stop)
    while not key_pressed:
        subprocess.run([python, 'createprofile.py', object_name, hr], stdout = subprocess.DEVNULL) #Run automated profile creation, muting prints
        
def extract_profile_data(prof_path):
    prof_file = open(prof_path, 'r') #Read prof file
    lines = prof_file.readlines() #Seperate lines
    prof_file.close() #Close file

    data = [x.strip() for x in lines[1].split(',')] #Extract and strip data line

    #Format data [Date, Star, Zen, Flux, See2, See, Fsee, Wind, tau0, theta0, scint, rms, prof*8]
    data_formatted = []

    #Convert first value to datetime
    data_formatted.append(datetime.fromisoformat(data[0]))

    #Convert second value to string
    data_formatted.append(data[1])

    #Convert next 10 values to float
    for value in data[2:12]:
        data_formatted.append(float(value))

    #Convert remaining values to a sublist (floats or np.nan)
    layers = []
    
    for value in data[12:]:
        if value.lower() == 'nan': #Deals with "nan" case (missing layer)
            layers.append(np.nan)
        else: #Deals with number case
            if float(value) == 0: #Deals with 0 case (treated as missing layer)
                layers.append(np.nan)  
            else: #Deals with actual value
                layers.append(float(value) * 1e-13)

    data_formatted.append(np.array(layers))

    return data_formatted

if __name__ == "__main__": #Check if python script is run directly
    if len(sys.argv) < 3: #Make sure correct inputs are given
        print('\033[91mError: Command should have format "python constobs.py {object_name} {hr_number}"\033[0m') #Error (red) print
        sys.exit()
  
    #Extract target information from input
    object_name = sys.argv[1] #Get object name
    hr = sys.argv[2] #Get HR number
    
    #Log start time
    timestamp = datetime.now(timezone.utc) #Get current time in UTC+0
    current_date = timestamp.strftime('%Y-%m-%d') #Extract date from timestamp
    start_time = timestamp.strftime('%H-%M-%S') #Extract time from timestamp
    
    continious_loop(object_name, hr) #Run continous profile generation
    
    #Log end time
    timestamp = datetime.now(timezone.utc) #Get current time in UTC+0
    end_time = timestamp.strftime('%H-%M-%S') #Extract time from timestamp
    
    #Extract z-grid from parameters file
    parameters_file = open(parameters_path, 'r') #Open parameters file
    parameters = json.load(parameters_file) #Extract parameters content
    parameters_file.close() #Close parameters file

    zgrid = np.array(parameters['profrest']['zgrid']) / 10**3 #Extract z-grid and set units to km
    
    #Initialise wanted data lists
    times = [] #Hold times for each profile
    layers = [] #Hold layer strengths for each profile
    seeings = [] #Hold seeing values for each profile
    
    #Collect data from profiles
    date_folder = os.path.join(outputs_path, current_date) #Find current date folder
    
    for time_folder_name in sorted(os.listdir(date_folder)):
        time_part = time_folder_name.split(' ')[0] #Extract the time part of the name
    
        if len(time_part.split('-')) != 3: #Skip folders that aren't time prefexed
            continue
    
        if time_part >= start_time: #Check if output made after observation started
            time_folder_path = os.path.join(date_folder, time_folder_name) #Get time folder path
            
            subfolders = [f for f in os.listdir(time_folder_path) if os.path.isdir(os.path.join(time_folder_path, f))] #Get all subfolders
            first_subfolder = os.path.join(time_folder_path, subfolders[0]) #Take first subfolder
    
            prof_path = glob.glob(os.path.join(first_subfolder, '*.prof'))[0] #Get .prof file
            
            prof_data = extract_profile_data(prof_path) #Get formatted profile data
            
            times.append(time_part) #Add time
            layers.append(prof_data[-1]) #Add layer strenghts
            seeings.append((prof_data[4], prof_data[5], prof_data[6])) #Add seeing values
            
    #Plot data over time
    datetimes = [datetime.strptime(t, '%H-%M-%S') for t in times] #Turn times from strings into datetime objects
    layers_sep = list(zip(*layers)) #Layers strengths seperated into layers
    seeings_sep = list(zip(*seeings)) #Seeing values seperated into types
    
    cmap = plt.get_cmap('Blues') #Use blue gradient
    layer_colours = [cmap(0.3 + 0.7 * (i / (len(zgrid) - 1))) for i in range(len(zgrid))] #Colours for each layer

    fig = plt.figure(figsize = (12, 6)) #Figure for layer strengths
    axes = [] #Hold layer axes
    layer_height = 1.0 / len(zgrid) #Vertical layer layout
    layer_bottoms = np.arange(len(zgrid)) * layer_height #Bottom of layers
    max_strength = max([max(layer) for layer in layers_sep]) * 1.1 #Find layer tops, based off maximum value
    for i in range(len(zgrid)): #Plot all layers
        ax = fig.add_axes([0.15, layer_bottoms[i], 0.8, layer_height])
        axes.append(ax) #Add axis
        ax.fill_between(datetimes, 0.01, layers_sep[i], color = layer_colours[i], alpha = 0.8) #Create under curve filling
        ax.set_yscale('log') #Set strength axis logarithmic
        ax.set_ylim(0.01, max_strength) #Set strenght axis limits
        if i != 0: #Give bottom layer time axis
            ax.set_xticks([])
        else:
            ax.set_xlabel('Time [H-M-S]', labelpad = 15) #Set x-axis label
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S')) #Format times on axis
            plt.setp(ax.get_xticklabels(), rotation = 90) #Make time labels vertical
        ax.spines['left'].set_position(('outward', 0)) #Attach y-axis to spine
        ax.spines['left'].set_visible(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False if i != 0 else True)
        ax.set_yticks([0.01, max_strength]) #Put altitude label on each layer
        ax.set_yticklabels([f'{zgrid[i]:.2f} km', ''])
        ax.tick_params(axis='y', which='both', left=True, labelleft=True) #Hide y-ticks, expect layer altitudes
        ax.set_xlim(datetimes[0], datetimes[-1]) #Set window to first and last data points
        
    plot_path = os.path.join(outputs_path, 'Turbulence Profile Plots', f'Layer Strengths - {start_time} to {end_time} - {object_name}.png') #Set plot path
    plt.savefig(plot_path, bbox_inches = 'tight') #Save plot (removing extra white-space)
    plt.close(fig) #Close plot
    
    fig = plt.figure(figsize = (12, 4)) #Figure for seeing values
    plt.plot(datetimes, seeings_sep[0], marker = 'o', label = '$\\epsilon_{\\text{diff}}$', color = 'red') #Plot differential motion seeing
    plt.plot(datetimes, seeings_sep[1], marker = 'o', label = '$\\epsilon_{\\text{scint}}$', color = 'blue') #Plot scintillation seeing
    plt.plot(datetimes, seeings_sep[2], marker = 'o', label = '$\\epsilon_{\\text{free}}$', color = 'purple') #Plot free atmosphere seeing
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S")) #Format times on axis
    plt.gcf().autofmt_xdate()  #Align time labels
    plt.xlabel('Time [H-M-S]', labelpad = 15) #Set x-axis label
    plt.ylabel('Seeing ($\\epsilon$) [\'\']', labelpad = 15) #Set y-axis label
    plt.xticks(rotation = 90) #Make time labels vertical
    plt.grid(True) #Add grid
    plot_path = os.path.join(outputs_path, 'Turbulence Profile Plots', f'Seeing Values - {start_time} to {end_time} - {object_name}.png') #Set plot path
    plt.savefig(plot_path, bbox_inches = 'tight') #Save plot (removing extra white-space)
    plt.close(fig) #Close plot