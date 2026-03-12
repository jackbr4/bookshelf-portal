# bookshelf-portal
Simple front end to allow multiple users to search and add books to Bookshelf (this can be made to work with Readarr with some minor adjustments). Search results will also inform the user if a book is already being monitored. This only works for searching books and not series. 

Due to the limitations of the Bookshelf API, when a book is added to be monitored, it will also monitor the author of the book and all their others books. An additional call is delivered to then unmonitor all the books from that author except the one initially selected. This can sometimes lead to additional titles by that author being added to Bookshelf. 

Future improvements would to be harden search (add addtional search options to Bookshelf and approve the monitoring/unmonitoring of books when an author is added. 

Simple log in screen
<img width="1225" height="874" alt="Login page" src="https://github.com/user-attachments/assets/62efd2c0-6a2f-4281-989b-7e28fef978db" />

Search page
<img width="1242" height="909" alt="Search page" src="https://github.com/user-attachments/assets/674b341f-e22d-4b7b-be5d-0048bdb5a35c" />

Search page with results
<img width="1200" height="900" alt="results page" src="https://github.com/user-attachments/assets/9fc4dd3b-fa59-47e3-b25d-613c23838e73" />

Book added or searched book is already monitored in Bookshelf
<img width="1184" height="878" alt="Book added or already in Bookshelf library" src="https://github.com/user-attachments/assets/69c5aa08-4d53-46d6-bcce-47cafebfb1b6" />
