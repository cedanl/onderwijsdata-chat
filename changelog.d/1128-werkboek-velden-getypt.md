### API: een object of lijst in een tekstveld van een werkboek geeft een 422 (#1128)
- `PUT /api/workbooks/{id}` met een object of lijst in `title`, `description`, `instelling`, `htmlContent` of
  `createdAt` (of een andere vorm dan een object in `dashboardSpec`) gaf een kale 500 bij de databasebinding. Die velden
  zijn nu getypt, zodat zo'n body de Nederlandse 422 van #637 krijgt en niets in het log zet.
