#Mossfly Bot

A local discord bot that can play music from YouTube.

##Installation
This bot requires *last.fm* and *discord* API keys to run in a file"api_keys.txt" stored in the same directory as the python file.



##Commands and Features
Commands are triggered with an exclamation mark.   
###Untested
❕Pause / ❕Resume    
Used to pause and unpause the audio.
❕Queuetop [song]   
Puts a song at the front of the queue.
❕Play [song]   
Plays a provided song or adds it to the queue.   
❕Undo   
Undoes a queued song.    
❕Skip   
Skips the currently playing song.    
❕Stop   
Stops playing and clears the queue.    
❕Shuffle    
Shuffles the queue.   
❕Deletequeue    
Command so nice I made it twice (see stop)    
❕Queue   
Shows the current queue.
❕Recommend [song artist - title]      
Queues up to 5 recommended songs based on a given song.    

###Known Issues
❕Volume    
Used to change the bot's output volume.    
Known issue: Not properly implemented.     

##Features to add
❔ A method of saving or loading queues as playlists.    
❔ Persistent queue - remembers your queue after disconnecting or stopping.       
➕ Better queue command: option for pages, removing individual songs.     
➕ More recommendation features: Autoplay mode, select how many songs, etc.    


## License
MIT License

Copyright (c) 2025 Dewi Payne

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.