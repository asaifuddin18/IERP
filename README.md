# IERP (Illini Esports Rewards Program)
Illini Esports Rewards Program (IERP) is a rewards program designed for Illini Esports, an RSO at the University of Illinois at Urbana-Champaign.  The goal of it is to increase engagement in the community through incentives, such as digital rewards through the Discord server. Rewards can be redeemed via points, which can be awarded by participating in various activities in the club.

## How to install
This project runs on Django, but does not have all the necessary files due to security reasons. In order to run your own, create a Django project and copy over the files from this project overriding any copies if needed. The rest of the dependencies can be installed via:

    pip install -r requirements.txt
Note: you will have to make an edit in discord/client.py:
Remove:
    self.loop = asyncio.get_event_loop() if loop is None else loop
and add:

    if loop is None:
	    self.loop = asyncio.new_event_loop()
	    asyncio.set_event_loop(self.loop)
    else:
    self.loop = loop
